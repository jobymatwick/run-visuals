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

logging.basicConfig(level="INFO")
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

    projection_max = project_web_mercator(bounds.lat_max, bounds.long_max)
    projection_min = project_web_mercator(bounds.lat_min, bounds.long_min)
    projection_range = (
        projection_max[0] - projection_min[0],
        projection_max[1] - projection_min[1],
    )
    logger.info(
        f"Real image area: "
        f"{projection_range[0]/1000:.1f} km x {projection_range[1]/1000:.1f} km"
        f" ({(projection_range[0]/1000)*(projection_range[1]/1000):.1f} km^2)"
    )

    i_width = 1200
    padding = (35, 35)
    stroke = 4
    opacity = 80

    i_height = int(i_width * (projection_range[1] / projection_range[0]))
    canvas_size = i_width - (2 * padding[0]), i_height - (2 * padding[1])

    logger.info(f"Image canvas area: {canvas_size[0]} px x {canvas_size[1]} px")
    logger.info(f"Scale: {projection_range[0] / canvas_size[0]:.1f} m/px")

    frames = [Image.new("RGB", (i_width, i_height), "white")]

    print("  -> Rendering frames /", end="", flush=True)
    spin = "/-\\|"
    colours = [(50,150,77), (155,209,198), (58,87,90), (192,225,92), (144,50,53), (16,237,220), (152,154,202), (73,56,142), (251,172,246), (152,103,246), (56,226,120), (207,123,93), (255,28,93), (250,206,117)]

    for i, section in enumerate(sections):
        active_frame = frames[-1].copy()
        draw = ImageDraw.ImageDraw(active_frame, "RGBA")
        draw_section(
            draw,
            section,
            projection_min,
            projection_range,
            canvas_size,
            padding,
            tuple(list(colours[i % len(colours)]) + [opacity]),
            stroke,
        )
        frames.append(active_frame)
        print(f"\b{spin[i % len(spin)]}", end="", flush=True)
    print("\r" + " " * 80 + "\r", end="", flush=True)

    logger.info("Saving GIF")
    frames[0].save(
        "out/animated.gif",
        save_all=True,
        append_images=frames[1:],
        duration=[500] * (len(frames) - 1) + [5000],
        optimize=True,
        loop=0,
    )
    logger.info(
        f"Output image size: "
        f"{os.stat('out/animated.gif').st_size / 1024 / 1024:.2f} MB"
    )


def draw_section(
    draw: ImageDraw.ImageDraw,
    section: Section,
    projection_min: tuple[float, float],
    projection_range: tuple[float, float],
    canvas_size: tuple[int, int],
    canvas_offset: tuple[int, int],
    colour: tuple[int, ...],
    line_width: float,
):
    pt_offset = int(line_width / 2)

    for point in section.points:
        pt_x_m, pt_y_m = point.project()
        pt_x_px, pt_y_px = (
            (
                math.floor(
                    ((pt_x_m - projection_min[0]) / projection_range[0])
                    * canvas_size[0]
                )
            )
            + canvas_offset[0],
            (
                (
                    -1
                    * math.floor(
                        ((pt_y_m - projection_min[1]) / projection_range[1])
                        * canvas_size[1]
                    )
                )
                + canvas_size[1]
            )
            + canvas_offset[1],
        )
        draw.ellipse(
            (
                (pt_x_px - pt_offset, pt_y_px - pt_offset),
                (pt_x_px + pt_offset, pt_y_px + pt_offset),
            ),
            colour,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-path", default=DEFAULT_RUN_PATH)
    parser.add_argument("-p", "--run-prefix", default=DEFAULT_RUN_PREFIX)
    args = parser.parse_args()
    main(args)
