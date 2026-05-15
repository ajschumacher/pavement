# Pavement plots

Quantile-based pavement plots with matplotlib. Every box contains an
equal share of the data.

![plot of four data sets](https://raw.githubusercontent.com/ajschumacher/pavement/main/examples/four_sets.png)

See more in the [demo notebook](https://github.com/ajschumacher/pavement/blob/main/examples/demo.ipynb).


## Install

    pip install pavement


## Usage

    import pavement
    pavement.plot([1, 2, 3, 4, 5])


## Tests

    pip install -e '.[test]'
    pytest
