import argparse
import os
import gpxpy
import logging
import math
from copy import deepcopy
from PIL import Image, ImageDraw
from typing import cast
import random
import time

from section import Section, project_web_mercator

logging.basicConfig(level="DEBUG")
logger = logging.getLogger(__name__)

DEFAULT_RUN_PATH = "/mnt/c/Users/joby/Documents/Runs/"
DEFAULT_RUN_PREFIX = "megameter"


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

    sections: list[Section] = []

    for run_file in run_files:
        with open(run_file, "r") as file_obj:
            g = gpxpy.parse(file_obj)
        points = g.tracks[0].segments[0].points
        section_id = 0
        while points:
            section, points = Section.from_gpx_track(
                points,
                f"{cast(str, g.tracks[0].name)}.{section_id}",
                min_spacing=0.0,
                max_speed=20.0,
                max_idle=30.0,
            )
            sections.append(section)
            section_id += 1

    bounds = deepcopy(sections[0].bounds)

    for section in sections:
        bounds.expand(section.bounds)

    x_max, y_max = project_web_mercator(bounds.lat_max, bounds.long_max)
    x_min, y_min = project_web_mercator(bounds.lat_min, bounds.long_min)
    x_range, y_range = (x_max - x_min, y_max - y_min)
    logger.info(
        f"Real image area: {x_range/1000:.1f}km x {y_range/1000:.1f}km ({(x_range/1000)*(y_range/1000):.1f}km^2)"
    )

    i_width = 2000
    i_height = int(i_width * (y_range / x_range))

    padding = 60
    canvas_width, canvas_height = i_width - (2 * padding), i_height - (2 * padding)

    line_width = 20
    pt_offset = int(line_width / 2)

    logger.info(f"Image pixel area: {canvas_width}px x {canvas_height}px")

    img = Image.new("RGB", (i_width, i_height), "white")
    draw = ImageDraw.ImageDraw(img, "RGBA")

    for section in sections:
        colour = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
            20,
        )
        for point in section.points:
            pt_x_m, pt_y_m = point.project()
            pt_x_px, pt_y_px = (
                (math.floor(((pt_x_m - x_min) / x_range) * canvas_width)) + padding,
                (
                    (-1 * math.floor(((pt_y_m - y_min) / y_range) * canvas_height))
                    + canvas_height
                )
                + padding,
            )
            draw.ellipse(
                (
                    (pt_x_px - pt_offset, pt_y_px - pt_offset),
                    (pt_x_px + pt_offset, pt_y_px + pt_offset),
                ),
                colour,
            )
    img.save("out/new.png")
    print("here")


# def draw_section(draw: ImageDraw.ImageDraw, section: Section):


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-path", default=DEFAULT_RUN_PATH)
    parser.add_argument("-p", "--run-prefix", default=DEFAULT_RUN_PREFIX)
    args = parser.parse_args()
    main(args)
