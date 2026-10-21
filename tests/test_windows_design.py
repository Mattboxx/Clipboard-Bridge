"""Raster-surface contracts: flat interiors, crisp edges and bounded controls."""

import clipboard_design as design


def test_button_surface_is_flat_not_a_stretched_gradient():
    image = design._surface("#202325", "#34393e")
    assert image.size == (32, 32)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((16, 0))[3] > 0
    interior = {image.getpixel((x, y)) for x in range(10, 22) for y in range(10, 22)}
    assert interior == {(32, 35, 37, 255)}


def test_switches_have_fixed_dimensions_in_every_state():
    colors = {"disabled": "#838b94", "primary": "#2769db", "scroll": "#626970"}
    for selected in (False, True):
        for disabled in (False, True):
            assert design._switch(colors, selected, disabled).size == (36, 22)
