import argparse
import os
import gpxpy
from gpxpy.gpx import GPXTrackPoint
import gpxpy.geo as geo
import logging
import datetime
import math
from copy import deepcopy
from PIL import Image, ImageDraw
import typing
import random

from run import Run, Section

logging.basicConfig(level="DEBUG")
logger = logging.getLogger(__name__)

DEFAULT_RUN_PATH = "/mnt/c/Users/joby/Documents/Runs/"
DEFAULT_RUN_PREFIX = "megameter"


def draw_sections(sections: typing.List[Section], i_width=500, padding=20):
    lower_bound = deepcopy(sections[0].bounds[0])
    upper_bound = deepcopy(sections[0].bounds[1])

    for section in sections:
        if section.bounds[1].x > upper_bound.x:
            upper_bound.x = section.bounds[1].x
        if section.bounds[1].y > upper_bound.y:
            upper_bound.y = section.bounds[1].y
        if section.bounds[0].x < lower_bound.x:
            lower_bound.x = section.bounds[0].x
        if section.bounds[0].y < lower_bound.y:
            lower_bound.y = section.bounds[0].y

    print(upper_bound)
    print(lower_bound)
    width = upper_bound.x - lower_bound.x
    height = upper_bound.y - lower_bound.y
    i_height = int(i_width * (height / width))
    print(f"width = {width:.2f} m, height = {height:.2f} m")
    print(f"width = {i_width} m, height = {i_height} m")

    img = Image.new("RGB", (i_width + (padding * 2), i_height + (padding * 2)), "white")
    draw = ImageDraw.Draw(img)

    for section in sections:
        colour = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
        for point in section.points:
            c = (
                int(((point.position.x - lower_bound.x) / width) * i_width) + padding,
                i_height
                - (int(((point.position.y - lower_bound.y) / height) * i_height)) + padding,
            )
            print(c)
            draw.point(c, colour)
    img.save("out/test.png")


def main(args):
    run_files = [
        os.path.join(args.input_path, gpx)
        for gpx in os.listdir(args.input_path)
        if gpx.startswith(args.run_prefix) and gpx.endswith(".gpx")
    ]
    run_files = sorted(
        run_files, key=lambda filename: int("".join(filter(str.isdigit, filename)))
    )
    logger.debug(f"Found {len(run_files)} runs with prefix '{args.run_prefix}'")

    sections = []

    for run_path in run_files:
        run = Run.from_gpx_file_path(run_path)
        sections += run.sections

    draw_sections(sections)
    return
    img = Image.new("RGB", (3000, 3000), "white")
    for p in run.sections[0].points:
        draw.ellipse(
            (
                ((int(p.position[0]) + 1500), (int(p.position[1]) + 2000)),
                ((int(p.position[0]) + 1500) + 10, (int(p.position[1]) + 2000) + 10),
            ),
            (0, 0, 0),
        )

    total_distance = 0
    num_points = 0
    for path in run_files:
        with open(path, "r") as run_file:
            gpx = gpxpy.parse(run_file)
            points = gpx.tracks[0].segments[0].points
            distance = 0
            last_point = points[0]
            for point in points[1:]:
                distance += last_point.distance_2d(point)
                last_point = point
            print(
                f"[{points[0].time.astimezone().strftime('%y-%m-%d %-I:%M %p')} "
                f"- {gpx.tracks[0].name}] {distance / 1000:.2f} km "
                f"(from {len(points)} points)"
            )
            total_distance += distance
            num_points += len(points)

    print(f"Total distance: {total_distance / 1000:.2f} km (from {num_points} points)")


def process_run(filename: str):
    with open(filename, "r") as run_file:
        gpx = gpxpy.parse(run_file)
    tracks = gpx.tracks

    logger.debug(
        f"Run file {os.path.basename(filename)} contains "
        f"{len(tracks)} track{'s' if len(tracks) - 1 else ''}"
    )

    for t_idx, track in enumerate(tracks):
        segments = track.segments
        logger.debug(
            f"Track {t_idx} contains "
            f"{len(segments)} segment{'s' if len(segments) - 1 else ''}"
        )

        for s_idx, segment in enumerate(segments):
            points = segment.points
            logger.debug(
                f"Segment {s_idx} contains "
                f"{len(points)} point{'s' if len(points) - 1 else ''}"
            )
            # When going through the points, we want to identify these areas:
            #   - still section: position does not change much over time (so
            #     that we can determine a "moving time", and to discard points
            #     that are in the same spot)
            #   - paused section: jump in distance from one point to the next
            #     (so the distance between pause and resume points does not
            #      count towards total distance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-path", default=DEFAULT_RUN_PATH)
    parser.add_argument("-p", "--run-prefix", default=DEFAULT_RUN_PREFIX)
    args = parser.parse_args()
    main(args)
