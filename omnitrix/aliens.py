"""Alien profiles. Colours, emblem, ambient effect and info-screen data per alien."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Alien:
    key: str
    name: str
    accent: str  # main theme colour
    secondary: str  # highlight colour
    bg_tint: str  # background tint for the alien's watch face
    emblem: str  # emblem drawer in omnitrix.emblems
    fx: str  # ambient / confirm effect in omnitrix.fx
    klass: str
    tagline: str
    stats: tuple[int, int, int]  # power, speed, defense (0-10)
    time_variation: str = "SemiBold Condensed"  # Bahnschrift style for the clock


ALIENS: list[Alien] = [
    Alien("heatblast", "HEATBLAST", "#FF6A13", "#FFC93C", "#1a0700", "flame", "embers", "PYROKINETIC",
          "Living flame. Hurls fireballs and rides columns of heat.", (8, 5, 5)),
    Alien("four_arms", "FOUR ARMS", "#FF2A2A", "#FF8A80", "#160202", "four_arms", "shock", "STRENGTH",
          "Four arms, twice the muscle. Claps out shockwaves.", (10, 3, 7), "Bold"),
    Alien("xlr8", "XLR8", "#1FA2FF", "#A8E6FF", "#010818", "bolt", "speed", "VELOCITY",
          "A blur on the street. Reflexes faster than sight.", (4, 10, 4), "Bold SemiCondensed"),
    Alien("diamondhead", "DIAMONDHEAD", "#3CF2FF", "#D2FFFF", "#011316", "crystal", "crystal", "CRYSTAL",
          "Living crystal. Grows blades and shields at will.", (7, 4, 9)),
    Alien("wildmutt", "WILDMUTT", "#FF8A1F", "#FFC27A", "#140900", "claws", "claws", "TRACKER",
          "Eyeless hunter. Tracks by scent and sound alone.", (6, 7, 5)),
    Alien("upgrade", "UPGRADE", "#7DFF2A", "#C8FFB0", "#0b0e0b", "circuit", "glitch", "TECHNO-ORGANIC",
          "Living tech. Merges with machines and upgrades them.", (5, 5, 6), "SemiBold"),
    Alien("ghostfreak", "GHOSTFREAK", "#B9A7FF", "#E8E0FF", "#07050f", "ghost", "mist", "SPECTRAL",
          "Phases through walls and fades from sight.", (5, 6, 8)),
    Alien("cannonbolt", "CANNONBOLT", "#F5E6A3", "#FFF7D6", "#100e05", "sphere", "roll", "ARMOURED",
          "Curls into an armoured ball and rolls through anything.", (7, 7, 10)),
    Alien("stinkfly", "STINKFLY", "#C6FF3A", "#EFFFB0", "#080d02", "wings", "buzz", "AERIAL",
          "Fast flyer. Rains sticky goo from above.", (5, 8, 4)),
    Alien("ripjaws", "RIPJAWS", "#19D6C0", "#9CFFF2", "#010d0e", "fin", "ripple", "AQUATIC",
          "Deep-sea predator. Unstoppable in the water.", (8, 6, 6)),
]

BY_KEY = {a.key: a for a in ALIENS}
