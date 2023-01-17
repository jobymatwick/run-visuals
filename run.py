from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import logging
import math
import os
from typing import TextIO, cast, Tuple, List

import gpxpy
from gpxpy import gpx as gpx_mod

logger = logging.getLogger(__name__)


class Run:
    def __init__(self, gpx: gpx_mod.GPX) -> None:
        """Create a run object from a GPX file path, GPX file object, or parsed
        gpxpy object.

        Args:
            gpx (Union[str, TextIO, gpx_mod.GPX]): GPX to generate run from.
              Accepts a path to the GPX file, a TextIO object of the GPX file,
              or a parsed GPX file from gpxpy.
        """
        self.process_gpx(gpx)

    @classmethod
    def from_gpx_file_path(cls, path: str) -> Run:
        with open(path, "r") as file:
            return Run.from_gpx_file(file)

    @classmethod
    def from_gpx_file(cls, file: TextIO) -> Run:
        return Run(gpxpy.parse(file))

    def process_gpx(self, gpx: gpx_mod.GPX) -> None:
        assert (
            len(gpx.tracks) == 1
        ), f"GPX object has {len(gpx.tracks)} track(s) (expected 1)"
        track = gpx.tracks[0]
        assert (
            len(track.segments) == 1
        ), f"Track has {len(track.segments)} segment(s) (expected 1)"
        self.name = track.name
        points = track.segments[0].points
        self.sections: List[Section] = []

        while len(points):
            section, points = Section.process_section(points)
            self.sections.append(section)


@dataclass
class Section:
    """A section is a continuous collection of points."""

    points: List[SectionPoint]
    """List of points in the section"""
    bounds: Tuple[Point, Point]
    """Minimum and maximum bounds of the section in meters"""
    distance: float
    """Total distance of the section"""

    @classmethod
    def process_section(
        cls,
        gpx_points: List[gpx_mod.GPXTrackPoint],
        duplicate_thresh=1.0,
        idle_thresh=15.0,
    ) -> Tuple[Section, List[gpx_mod.GPXTrackPoint]]:
        """Process a list of GPS coordinates and use them to create a section.
        Stop when the list is fully consumed or the section ends. Duplicate
        points are omitted.

        Args:
            gpx_points (List[gpx_mod.GPXTrackPoint]): List of GPX points to get
              a section from
            duplicate_thresh (float): Minimum distance between points. If not
              exceeded, the point is omitted
            idle_thresh (float): Max time between points before ending the
              section

        Returns:
            Tuple[Section, List[gpx_mod.GPXTrackPoint]]: Processed section and
              list of points not used in the new section
        """
        projected: List[SectionPoint] = [SectionPoint.from_gpx_point(gpx_points[0])]
        lower_bound = deepcopy(projected[0].position)
        upper_bound = deepcopy(projected[0].position)
        ending_reason = "all points consumed"
        ommitted_total = 0
        ommitted_count = 0
        point_id = 0
        total_distance = 0

        for point_id, point in enumerate(gpx_points[1:]):
            new_point = SectionPoint.from_gpx_point(point)
            dist_from_prev = new_point.position.distance(projected[-1].position)

            if dist_from_prev <= duplicate_thresh:
                ommitted_total += dist_from_prev
                ommitted_count += 1
                continue

            total_distance += dist_from_prev

            idle_time = new_point.time - projected[-1].time
            if idle_time > idle_thresh:
                ending_reason = (
                    f"idle time of {idle_time:.2f}s exceeds "
                    f"threshold of {idle_thresh:.2f}s"
                )
                point_id -= 1
                break

            if new_point.position.x > upper_bound.x:
                upper_bound.x = new_point.position.x
            if new_point.position.y > upper_bound.y:
                upper_bound.y = new_point.position.y
            if new_point.position.x < lower_bound.x:
                lower_bound.x = new_point.position.x
            if new_point.position.y < lower_bound.y:
                lower_bound.y = new_point.position.y
            projected.append(new_point)

        logger.debug(f"Section ended ({ending_reason}, {len(projected)} points)")

        if ommitted_count:
            logger.debug(
                f"Ommitted {ommitted_count} points (average of "
                f"{ommitted_total / ommitted_count:.2f} m from previous point)"
            )

        return (
            Section(projected, (lower_bound, upper_bound), total_distance),
            gpx_points[(point_id + 2) :],
        )

    def to_csv(self, outfile):
        with open(outfile, "w") as out:
            out.write("x,y\n")
            for p in self.points:
                out.write(f"{p.position.x},{p.position.y}\n")


@dataclass
class SectionPoint:
    position: Point
    """x-y postion in meters"""
    elevation: float
    """elevation in meters"""
    time: float
    """Time in seconds"""
    extensions: dict
    """Dictionary of any extensionstp and their values"""

    @classmethod
    def from_gpx_point(cls, gpx_point: gpx_mod.GPXTrackPoint) -> SectionPoint:
        return SectionPoint(
            position=Point.web_mercator(gpx_point),
            elevation=gpx_point.elevation,
            time=cast(datetime, gpx_point.time).timestamp(),
            extensions=(
                {
                    ext.tag.rsplit("}", 1)[-1]: ext.text
                    for ext in gpx_point.extensions[0]
                }
                if gpx_point.extensions
                else {}
            ),
        )


@dataclass
class Point:
    x: float
    y: float

    @classmethod
    def web_mercator(cls, gpx_pt: gpx_mod.GPXTrackPoint) -> Point:
        """Convert GPS coordinates to XY coordinate in meters using the web a
        Psuedo-Mercator progection (commonly known as "Web-Mercator").
        Implementation based on https://wiki.openstreetmap.org/wiki/Mercator#Python.

        Args:
            gpx_pt (gpx_mod.GPXTrackPoint): GPS coordinate

        Returns:
            Point: Projected XY coordinates in meters
        """
        EARTH_RADIUS_M = 6.3781e6

        return Point(
            math.radians(gpx_pt.longitude) * EARTH_RADIUS_M,
            math.log(math.tan(math.pi / 4 + math.radians(gpx_pt.latitude) / 2))
            * EARTH_RADIUS_M,
        )

    def distance(self, point: Point) -> float:
        """Calculate the absolute distance between two points

        Args:
            point (Point): Point to calculate the distance between

        Returns:
            float: absolute distance
        """
        return math.sqrt(math.pow(self.x - point.x, 2) + math.pow(self.y - point.y, 2))
