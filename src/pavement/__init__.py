from collections import Counter

import matplotlib.pyplot as plt


def quantiles(data, levels, weights=None, presorted=False):
    """Type 2 quantiles, possibly weighted"""
    # https://robjhyndman.com/papers/sample_quantiles.pdf
    if not all(0 <= a < b <= 1 for a, b in zip(levels, levels[1:])):
        raise ValueError("levels must be strictly increasing in [0, 1]")
    if not presorted:
        if weights is None:
            data = sorted(data)
        else:
            data, weights = zip(*sorted(zip(data, weights)))
    total = len(data) if weights is None else sum(weights)
    targets = [level * total for level in levels]
    level_index = 0
    value = float('-inf')
    cumulative = 0
    results = []
    for index in range(len(data)):
        if data[index] < value:
            raise ValueError("data must be sorted")
        value = data[index]
        weight = 1 if weights is None else weights[index]
        if weight <= 0:
            raise ValueError("weights must be positive")
        cumulative += weight
        while level_index < len(levels) and cumulative > targets[level_index]:
            results.append(value)
            level_index += 1
        if level_index < len(levels) and cumulative == targets[level_index]:
            next_value = data[index + 1] if index + 1 < len(data) else value
            results.append((value + next_value) / 2)
            level_index += 1
    return results


def draw_pavement(values, ypos=0, height=0.6,
                  whisker=0.1, show_whiskers=True):
    plt.vlines(values,
               ymin=ypos - height/2, ymax=ypos + height/2,
               color='black')
    if show_whiskers:
        dupes = [x for x, n in Counter(values).items() if n > 1]
        if dupes:
            plt.vlines(dupes,
                       ymin=ypos - height/2 - whisker,
                       ymax=ypos + height/2 + whisker,
                       color='black')
    plt.hlines([ypos - height/2, ypos + height/2],
               xmin=values[0], xmax=values[-1],
               color='black')


def pavement_stats(data, bins=4, weights=None):
    levels = [x/bins for x in range(bins + 1)]
    return quantiles(data, levels, weights)


def plot(data, weights=None, categories=None, labels=None,
         bins=4, ypos=0, height=0.6,
         whisker=0.1, show_whiskers=True):
    if categories is not None:
        if labels is None:
            labels = sorted(set(categories))
        data = [[d for d, c in zip(data, categories) if c == label]
                for label in labels]
        if weights is not None:
            weights = [[w for w, c in zip(weights, categories) if c == label]
                       for label in labels]
    if not hasattr(data[0], '__iter__'):
        data = [data]
        weights = [weights] if weights is not None else None
    n = len(data)
    for index, dataset in enumerate(data):
        subweights = weights[index] if weights is not None else None
        values = pavement_stats(dataset, bins=bins, weights=subweights)
        draw_pavement(values, ypos=ypos + n - 1 - index, height=height,
                      whisker=whisker, show_whiskers=show_whiskers)
    if labels is not None:
        plt.gca().set_yticks(range(ypos, ypos + n), list(reversed(labels)))
