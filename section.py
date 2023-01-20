from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from gpxpy import gpx as gpx_mod
from gpxpy import geo
from typing import cast, Union
import math

logger = logging.getLogger(__name__)


@dataclass
class Section:
    name: str
    points: list[SectionPoint]
    stats: SectionStats
    bounds: SectionBounds

    @classmethod
    def from_gpx_track(
        cls,
        gpx_points: list[gpx_mod.GPXTrackPoint],
        name: str,
        min_spacing: float = 1,
        max_speed: float = 10,
        max_idle: float = 30,
    ) -> tuple[Section, list[gpx_mod.GPXTrackPoint]]:
        """Create a section from a list of GPX track points

        Args:
            gpx (list[gpx_mod.GPXTrackPoint]): List of GPX track points to
              create the section from.
            name (str): Name for the created section.
            min_spacing (float): Minimum distance in meters between adjacent
              points. Points that are any closer are discarded.
            max_speed (float): Max speed in meters per second from one point to
              the next. Points that exceed this are omitted. This is to filter
              out errant points.
            max_idle (float): Max time in seconds between two valid points that
              can elapse before the section is considered over.

        Returns:
            tuple[Section, list[gpx_mod.GPXTrackPoint]]: Created section, list
              of unused remaining track points, if they were not all consumed
        """
        collected_points = [SectionPoint.from_gpx_point(gpx_points[0])]
        stats = SectionStats(0)
        bounds = SectionBounds.from_point(collected_points[-1])
        point_idx = 0
        ending_reason = "all points consumed"
        for point_idx, point in enumerate(gpx_points[1:]):
            prev_point = collected_points[-1]
            distance = geo.distance(
                point.latitude,
                point.longitude,
                point.elevation,
                prev_point.lat,
                prev_point.long,
                prev_point.elev,
            )
            if distance < min_spacing:
                logger.debug(
                    f"Discarding point {point_idx + 1} as it is only "
                    f"{distance:.2f} m from the previous point"
                )
                continue

            elapsed = cast(datetime, point.time).timestamp() - prev_point.time
            speed = distance / elapsed
            if speed > max_speed:
                logger.debug(
                    f"  -> Discarding point {point_idx + 1} as it has an "
                    f"excessive speed ({speed:.2f} m/s)"
                )
                continue

            if elapsed > max_idle:
                ending_reason = f"idle period of {int(elapsed)} seconds"
                point_idx -= 1
                break

            collected_points.append(SectionPoint.from_gpx_point(point))
            bounds.expand(collected_points[-1])
            stats.distance += distance

        logger.info(
            f"'{name}': {len(collected_points)} points "
            f"({point_idx - (len(collected_points) - 2)} discarded, "
            f"ended because {ending_reason})"
        )
        return (
            Section(name, collected_points, stats, bounds),
            gpx_points[point_idx + 2 :],
        )


@dataclass
class SectionPoint:
    lat: float
    long: float
    elev: float
    time: float

    @classmethod
    def from_gpx_point(cls, gpx_point: gpx_mod.GPXTrackPoint) -> SectionPoint:
        return SectionPoint(
            gpx_point.latitude,
            gpx_point.longitude,
            gpx_point.elevation,
            cast(datetime, gpx_point.time).timestamp(),
        )

    def project(self) -> tuple[float, float]:
        return project_web_mercator(self.lat, self.long)


def project_web_mercator(lat: float, long: float) -> tuple[float, float]:
    EARTH_RADIUS_M = 6.3781e6

    return (
        math.radians(long) * EARTH_RADIUS_M,
        math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * EARTH_RADIUS_M,
    )


@dataclass
class SectionBounds:
    lat_min: float
    lat_max: float
    long_min: float
    long_max: float

    @classmethod
    def from_point(cls, point: SectionPoint) -> SectionBounds:
        return SectionBounds(
            point.lat,
            point.lat,
            point.long,
            point.long,
        )

    def expand(self, expand_with: Union[SectionPoint, SectionBounds]) -> None:
        points: list[SectionPoint] = []
        if type(expand_with) == SectionPoint:
            points = [cast(SectionPoint, expand_with)]
        elif type(expand_with) == SectionBounds:
            bounds = cast(SectionBounds, expand_with)
            points = [
                SectionPoint(bounds.lat_min, bounds.long_min, 0, 0),
                SectionPoint(bounds.lat_max, bounds.long_max, 0, 0),
            ]

        for point in points:
            if point.lat < self.lat_min:
                self.lat_min = point.lat
            elif point.lat > self.lat_max:
                self.lat_max = point.lat

            if point.long < self.long_min:
                self.long_min = point.long
            elif point.long > self.long_max:
                self.long_max = point.long


@dataclass
class SectionStats:
    distance: float
