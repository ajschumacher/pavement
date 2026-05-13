from collections import Counter

import matplotlib.pyplot as plt


def quantiles(data, levels, weights=None):
    """Type 2 quantiles for sorted data, possibly weighted"""
    # https://robjhyndman.com/papers/sample_quantiles.pdf
    if not all(0 <= a < b <= 1 for a, b in zip(levels, levels[1:])):
        raise ValueError("levels must be strictly increasing in [0, 1]")
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


def sort(data, weights=None):
    if weights is None:
        return sorted(data), None
    data, weights = zip(*sorted(zip(data, weights)))
    return data, weights


def plot(data, weights=None,
         bins=4, ypos=0, height=0.6,
         whisker=0.1, show_whiskers=True):
    levels = list(x/bins for x in range(bins + 1))
    data, weights = sort(data, weights)
    values = quantiles(data, levels, weights)
    plt.vlines(values,
               ymin=ypos - height/2, ymax=ypos + height/2,
               color='black')
    dupes = [x for x, n in Counter(values).items() if n > 1]
    if dupes and show_whiskers:
        plt.vlines(dupes,
                   ymin=ypos - height/2 - whisker,
                   ymax=ypos + height/2 + whisker,
                   color='black')
    plt.hlines([ypos - height/2, ypos + height/2],
               xmin=values[0], xmax=values[-1],
               color='black')

def multi(data, categories, labels=None, weights=None,
          bins=4, height=0.6,
          whisker=0.1, show_whiskers=True):
    if labels is None:
        labels = sorted(list(set(categories)))
    for index, label in enumerate(labels[::-1]):
        subdata = [d for d, c in zip(data, categories) if c == label]
        subweights = ([w for w, c in zip(weights, categories) if c == label]
                      if weights is not None else None)
        plot(subdata, weights=subweights, bins=bins, ypos=index, height=height,
             whisker=whisker, show_whiskers=show_whiskers)
    plt.gca().set_yticks(list(range(len(labels))), labels[::-1])
