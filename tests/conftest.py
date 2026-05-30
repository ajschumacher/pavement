# Use a headless backend for the matplotlib tests. matplotlib is now an
# optional backend, so tolerate its absence — its tests importorskip it.
try:
    import matplotlib

    matplotlib.use("Agg")
except ImportError:
    pass
