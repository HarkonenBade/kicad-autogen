#! /usr/bin/env python
"""
build_lib_ic.py
Copyright 2016 Adam Greig
Licensed under the MIT licence, see LICENSE file for details.

Generate symbols for generic black-box ICs etc.

Symbols configuration:
Each symbol is defined by a .yaml file in the same path that the .lib file
should be placed. Each file contains the following keys:
designator: optional, default "IC", the default reference designator
footprint: optional, an associated footprint to autofill
datasheet: optional, a URL or path to a datasheet
ordercodes: optional, list of (supplier, code) for supplier order codes
description: description of the part, placed in the .dcm file
pins: list of lists of left and right pin groups
          (blocks of related pins with a space in-between).
      Each group contains a list of tuples of:
          (pin name, pin number, electrical type).
      Number and name may be given as a string or an integer.
      Electrical type must be a string out of:
          in, out, bidi, tri, passive, unspec, pwrin, pwrout,
          oc, od, oe, os, nc.
      These correspond to input, output, bidirectional, tristate, passive,
          unspecified, power_input, power_output, open_collector,
          open_emitter, and not_connected. They should be given as strings.

"""

from __future__ import print_function, division

import os
import sys
import yaml
import fnmatch
import argparse
import pathlib

pin_types = {
    "in": "I",
    "out": "O",
    "bidi": "B",
    "tri": "T",
    "passive": "P",
    "unspec": "U",
    "pwrin": "W",
    "pwrout": "w",
    "oc": "C",
    "od": "C",
    "oe": "E",
    "os": "E",
    "nc": "N",
}


def longest_num(units):
    return max(max(
        max([0] + [max(len(str(p[1])) for p in grp) for grp in left_pins]),
        max([0] + [max(len(str(p[1])) for p in grp) for grp in right_pins]))
        for (left_pins, right_pins) in units)


def geometry(unit, longest_num):
    left_pins, right_pins = unit

    length = max(100, longest_num * 50)

    # Find longest name of all pins
    longest_name = max(
        max([0] + [max(len(p[0]) for p in grp) for grp in left_pins]),
        max([0] + [max(len(p[0]) for p in grp) for grp in right_pins]))

    # Width is either that required for longest name or twice that for
    # dual-sided parts, rounded up to nearest 100. If length is not a
    # multiple of 100, add extra width to ensure pins are on 0.1" grid.
    width = (longest_name + 1) * 50
    width += width % 100
    if left_pins and right_pins:
        width *= 2
    if ((width//2)+length) % 100 != 0:
        width += 2 * (((width//2)+length) % 100)

    # Height is maximum required between each side
    n_left_pins = sum(len(grp) for grp in left_pins)
    n_right_pins = sum(len(grp) for grp in right_pins)
    n_left_groups = len(left_pins)
    n_right_groups = len(right_pins)
    height = 100 * max(
        n_left_pins + n_left_groups - 1, n_right_pins + n_right_groups - 1)

    # Ensure height is an odd multiple of 0.1" to keep everything aligned
    # to the 0.1" grid. This is responsible for the unseemly gaps at the
    # bottom of parts with an even number of pins, but preserves symmetry.
    if (height // 100) % 2 == 0:
        height += 100

    return width, height, length


def normalise_pins(pins):
    """
    Convert YAML representation of pins into a normal structure, which is
    a list of (left, right) tuples, where each tuple is a symbol unit,
    and left and right are either empty lists, or lists of groups,
    where each group is a list of [name, number, type] pins.
    """
    output = []
    # Get what might be either the first pin or the first group of pins,
    # depending on whether the list is 3 deep (one unit) or 4 (multiple units)
    first_pin_or_grp = pins[0][0][0]
    if first_pin_or_grp is None:
        # For right-hand-only parts, we might need to check the second entry
        first_pin_or_grp = pins[1][0][0]
    if isinstance(first_pin_or_grp[0], str):
        # Str means a name, so this is a pin, so there's only
        # one unit, so wrap in a new list.
        pins = [pins]
    for unit in pins:
        if len(unit) == 1:
            # Only one side: left groups only
            output.append((unit[0], []))
        elif len(unit) == 2:
            if unit[0][0][0] is None:
                # Empty left side: right groups only
                output.append(([], unit[1]))
            else:
                # Both sides
                output.append((unit[0], unit[1]))
        else:
            raise ValueError("Invalid pins")
    return output


def fields(conf, units):
    n = longest_num(units)
    geoms = [geometry(unit, n) for unit in units]
    width = max(g[0] for g in geoms)
    height = max(g[1] for g in geoms)
    field_x = -width//2
    field_y = height//2 + 50
    out = []

    # Designator at top
    out.append("F0 \"{}\" {} {} 50 H V L CNN".format(
        conf.get('designator', 'IC'), field_x, field_y))

    # Value/name at bottom
    out.append("F1 \"{}\" {} {} 50 H V L CNN".format(
        conf['name'], field_x, -field_y))

    # Either specify a footprint or just set its size, position, invisibility
    if "footprint" in conf:
        out.append("F2 \"{}\" {} {} 50 H I L CNN".format(
            conf['footprint'], field_x, -field_y-100))
    else:
        out.append("F2 \"\" {} {} 50 H I L CNN".format(field_x, -field_y-100))

    # Specify a datasheet if given
    if "datasheet" in conf:
        out.append("F3 \"{}\" {} {} 50 H I L CNN".format(
            conf['datasheet'], field_x, -field_y-200))
    else:
        out.append("F3 \"\" {} {} 50 H I L CNN".format(field_x, -field_y-200))

    # Order codes
    for idx, (supplier, code) in enumerate(conf.get("ordercodes", [])):
        out.append("F{} \"{}\" {} {} 50 H I L CNN \"{}\"".format(
            idx+4, code, field_x, -field_y-(300+idx*100), supplier))

    return out


def draw_pins(groups, x0, y0, direction, length, unit_idx):
    out = []
    pin_x = x0
    pin_y = y0
    for group in groups:
        for (name, num, t) in group:
            out.append("X {} {} {} {} {} {} 50 50 {} 0 {}".format(
                name, num, pin_x, pin_y, length, direction, unit_idx,
                pin_types[t]))
            pin_y -= 100
        pin_y -= 100
    return out


def draw(units):
    out = []
    out.append("DRAW")

    n = longest_num(units)

    for unit_idx, unit in enumerate(units):
        if len(units) > 1:
            # For multi-unit parts, unit indices start at 1,
            # while for single-unit parts, everythign is unit 0.
            unit_idx += 1
        width, height, length = geometry(unit, n)

        # Containing box
        out.append("S {} {} {} {} {} 1 0 f".format(
            -width//2, height//2, width//2, -height//2, unit_idx))

        # Pins
        x0 = -width//2 - length
        y0 = height//2 - 50
        left_pins, right_pins = unit
        if left_pins:
            out += draw_pins(left_pins, x0, y0, "R", length, unit_idx)
        if right_pins:
            out += draw_pins(right_pins, -x0, y0, "L", length, unit_idx)

    out.append("ENDDRAW")
    return out


def library(conf):
    out = []

    if not isinstance(conf, list):
        conf = [conf]
    

    out.append("EESchema-LIBRARY Version 2.3")
    out.append("#encoding utf-8")
    for elm in conf:
        units = normalise_pins(elm['pins'])
        out.append("#\n# {}\n#".format(elm['name']))
        locked = "F" if len(units) == 1 else "L"
        out.append("DEF {} {} 0 40 Y Y {} {} N".format(
            elm['name'], elm.get('designator', 'IC'), len(units), locked))

        out += fields(elm, units)
        out += draw(units)

        out.append("ENDDEF")
    out.append("#\n#End Library\n")
    return "\n".join(out)


def documentation(conf):
    out = []
    
    if not isinstance(conf, list):
        conf = [conf]
    
    out.append("EESchema-DOCLIB  Version 2.0")
    for elm in conf:
        out.append("$CMP {}".format(elm['name']))
        out.append("D {}".format(elm['description']))
        if "datasheet" in elm:
            out.append("F {}".format(elm['datasheet']))
        out.append("$ENDCMP")
    return "\n".join(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('infile', type=str, default="-")
    args = vars(parser.parse_args())
    if args['infile'] != "-":
        name = pathlib.PurePath(args['infile'])
    else:
        name = pathlib.PurePath("./built_lib")

    if args['infile'] == "-":
        cfg = yaml.safe_load(sys.stdin)
    else:
        with open(args['infile'], "r") as f:
            cfg = yaml.safe_load(f)

    lib = library(cfg)
    doc = documentation(cfg)

    with open(name.with_suffix(".lib"), "w") as f:
        f.write(lib)

    with open(name.with_suffix(".dcm"), "w") as f:
        f.write(doc)

