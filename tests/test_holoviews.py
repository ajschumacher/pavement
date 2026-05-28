import pytest

hv = pytest.importorskip("holoviews")

from pavement.holoviews import pavement, pavement_elements  # noqa: E402


@pytest.fixture(autouse=True)
def _bokeh_backend():
    # A backend must be active for .opts() to resolve option names.
    hv.extension("bokeh")


def test_elements_returns_rectangles_and_no_whiskers():
    rects, whiskers = pavement_elements([1, 2, 3, 4, 5])
    assert isinstance(rects, hv.Rectangles)
    assert len(rects) == 4  # 4 bins -> 4 rectangles
    assert whiskers is None  # no repeated quantile values


def test_elements_whiskers_on_repeated_values():
    # Heavy repetition forces coincident quantile edges -> whiskers.
    rects, whiskers = pavement_elements([0, 0, 0, 0, 1, 2, 3], bins=4)
    assert isinstance(whiskers, hv.Segments)
    assert len(whiskers) > 0


def test_elements_band_vdim_reports_quantile_span():
    rects, _ = pavement_elements([1, 2, 3, 4, 5], bins=4)
    assert list(rects.dimension_values("band")) == [
        "0%–25%", "25%–50%", "50%–75%", "75%–100%"]


def test_elements_horizontal_swaps_axes():
    vert, _ = pavement_elements([1, 2, 3, 4, 5], orientation="vertical")
    horiz, _ = pavement_elements([1, 2, 3, 4, 5], orientation="horizontal")
    # The value range lands on y for vertical, on x for horizontal.
    assert list(vert.dimension_values("y0")) == list(
        horiz.dimension_values("x0"))


def test_elements_bins_none_is_a_rug():
    rects, _ = pavement_elements([1, 2, 3, 4, 5], bins=None)
    assert len(rects) == 4  # one band between each pair of points


def test_pavement_single_returns_overlay():
    result = pavement([1, 2, 3, 4, 5])
    assert isinstance(result, hv.Overlay)


def test_pavement_multiple_returns_ndoverlay_keyed_by_label():
    result = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
    assert isinstance(result, hv.NdOverlay)
    assert list(result.keys()) == ["a", "b"]


def test_pavement_tidy_splits_by_category():
    result = pavement([1, 2, 3, 4, 5, 6],
                      categories=["x", "x", "x", "y", "y", "y"])
    assert isinstance(result, hv.NdOverlay)
    assert list(result.keys()) == ["x", "y"]


def test_pavement_per_row_bins_mix_none_and_int():
    result = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], bins=[None, 2],
                      labels=["a", "b"])
    assert len(result["a"].Rectangles.I) == 3  # all data: 3 bands
    assert len(result["b"].Rectangles.I) == 2  # 2 bins


def test_pavement_renders_across_backends():
    # The same definition renders through every backend; styling resolves
    # against whichever backend is active when the plot is built (the
    # usual HoloViews pattern of choosing the backend up front).
    for backend in ("bokeh", "matplotlib", "plotly"):
        hv.extension(backend)
        obj = pavement([[1, 2, 3, 4], [5, 6, 7, 8]], labels=["a", "b"])
        # Should not raise; returns a backend-native figure object.
        assert hv.render(obj, backend=backend) is not None


def test_pavement_bokeh_has_hover_with_clean_tooltips():
    obj = pavement([1, 2, 3, 4, 5])
    fig = hv.render(obj, backend="bokeh")
    hovers = [t for t in fig.toolbar.tools if type(t).__name__ == "HoverTool"]
    assert hovers, "expected a hover tool on the bokeh figure"
    fields = [name for name, _ in hovers[0].tooltips]
    assert fields == ["band", "low", "high"]  # not the raw x0/y0 corners


def test_pavement_empty_data():
    with pytest.raises(ValueError, match="empty"):
        pavement([])


def test_pavement_positions_length_mismatch():
    with pytest.raises(ValueError, match="positions"):
        pavement([[1, 2], [3, 4]], positions=[1])


def test_pavement_bins_length_mismatch():
    with pytest.raises(ValueError, match="bins"):
        pavement([[1, 2], [3, 4]], bins=[4])


def test_pavement_color_length_mismatch():
    with pytest.raises(ValueError, match="color"):
        pavement([[1, 2], [3, 4]], color=["red"])


def test_pavement_labels_length_mismatch():
    with pytest.raises(ValueError, match="labels"):
        pavement([[1, 2], [3, 4]], labels=["only-one"])
