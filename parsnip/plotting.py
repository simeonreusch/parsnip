from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec
from sklearn.metrics import confusion_matrix
import itertools
import numpy as np
import avocado

from . import preprocess_light_curve


def plot_light_curve(light_curve, model=None, count=100, show_uncertainty_bands=True,
                     show_missing_bandpasses=False, percentile=68, ax=None, **kwargs):
    # TODO: for unpreprocessed light curves, show the model in the original units.
    if not light_curve.meta.get('parsnip_preprocessed', False) and model is not None:
        light_curve = preprocess_light_curve(light_curve, model.settings)

    if ax is None:
        fig, ax = plt.subplots(figsize=(5, 4), constrained_layout=True)

    used_bandpasses = []

    band_groups = light_curve.group_by('band').groups
    for band_name, band_data in zip(band_groups.keys['band'], band_groups):
        if len(band_data) == 0:
            continue

        # TODO: Drop avocado dependency
        c = avocado.get_band_plot_color(band_name)
        marker = avocado.get_band_plot_marker(band_name)

        ax.errorbar(band_data['time'], band_data['flux'], band_data['fluxerr'],
                    fmt='o', c=c, label=band_name, elinewidth=1, marker=marker)

        used_bandpasses.append(band_name)

    if model is not None:
        max_model = 0.
        label_model = True

        model_times, model_flux, model_result = model.predict_light_curve(
            light_curve, count, **kwargs
        )

        for band_idx, band_name in enumerate(model.settings['bands']):
            if band_name not in used_bandpasses and not show_missing_bandpasses:
                continue

            c = avocado.get_band_plot_color(band_name)
            marker = avocado.get_band_plot_marker(band_name)

            if label_model:
                label = 'ParSNIP Model'
                label_model = False
            else:
                label = None

            if count == 0:
                # Single prediction
                ax.plot(model_times, model_flux[band_idx], c=c, label=label)
                band_max_model = np.max(model_flux[band_idx])
            elif show_uncertainty_bands:
                # Multiple predictions, show error bands.
                percentile_offset = (100 - percentile) / 2.
                flux_median = np.median(model_flux[:, band_idx], axis=0)
                flux_min = np.percentile(model_flux[:, band_idx], percentile_offset,
                                         axis=0)
                flux_max = np.percentile(model_flux[:, band_idx],
                                         100 - percentile_offset, axis=0)
                ax.plot(model_times, flux_median, c=c, label=label)
                ax.fill_between(model_times, flux_min,
                                flux_max, color=c, alpha=0.3)
                band_max_model = np.max(flux_median)
            else:
                # Multiple predictions, show raw light curves
                ax.plot(model_times, model_flux[:, band_idx].T, c=c, alpha=0.1)
                band_max_model = np.max(model_flux)

            max_model = max(max_model, band_max_model)

        ax.set_ylim(-0.2 * max_model, 1.2 * max_model)

    ax.legend()
    ax.set_xlabel('Time (days)')
    ax.set_ylabel('Flux')


def plot_spectrum(model, light_curve, time, count=100, show_bands=True, percentile=68,
                  ax=None, c=None, label=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)

    model_wave = model.model_wave
    model_spectra = model.predict_spectrum(light_curve, time, count)

    if count == 0:
        # Single prediction
        ax.plot(model_wave, model_spectra, c=c, label=label)
    elif show_bands:
        # Multiple predictions, show error bands.
        percentile_offset = (100 - percentile) / 2.
        flux_median = np.median(model_spectra, axis=0)
        flux_min = np.percentile(model_spectra, percentile_offset, axis=0)
        flux_max = np.percentile(
            model_spectra, 100 - percentile_offset, axis=0)
        ax.plot(model_wave, flux_median, c=c, label=label)
        ax.fill_between(model_wave, flux_min, flux_max, color=c, alpha=0.3)
    else:
        # Multiple predictions, show raw light curves
        ax.plot(model_wave, model_spectra.T, c=c, alpha=0.1)

    ax.set_xlabel('Wavelength ($\\AA$)')
    ax.set_ylabel('Flux')


def plot_confusion_matrix(predictions, classifications, figsize=(5, 4), title=None):
    """Plot a confusion matrix

    Adapted from example that used to be at
    http://scikit-learn.org/stable/modules/generated/sklearn.metrics.confusion_matrix.html
    """
    if len(classifications.columns) == 2 and classifications.columns[0] == 'Other':
        # Single class classification. All labels other than the target one are grouped
        # as "Other".
        target_label = classifications.columns[1]
        match_labels = predictions['label'] == target_label
        labels = match_labels.replace({False: 'Other', True: target_label})
    else:
        labels = predictions['label']

    class_names = classifications.columns

    plt.figure(figsize=figsize, constrained_layout=True)
    cm = confusion_matrix(labels, classifications.idxmax(axis=1),
                          labels=class_names, normalize='true')

    im = plt.imshow(cm, interpolation='nearest',
                    cmap=plt.cm.Blues, vmin=0, vmax=1)
    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names, rotation=60, ha='right')
    plt.yticks(tick_marks, class_names)

    fmt = '.2f'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")

    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    if title is not None:
        plt.title(title)

    # Make a colorbar that is lined up with the plot
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    ax = plt.gca()
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="4%", pad=0.25)
    plt.colorbar(im, cax=cax, label='Fraction of objects')


def plot_representation(predictions, plot_labels, mask=None, idx1=1, idx2=2, idx3=None,
                        max_count=1000, show_legend=True, legend_ncol=1, marker=None,
                        markersize=5, ax=None):
    """Plot a representation"""
    color_map = {
        'SNIa': 'C0',
        'SNIax': 'C9',
        'SNIa-91bg': 'lightgreen',

        'SLSN': 'C2',
        'SNII': 'C1',
        'SNIIn': 'C3',
        'SNIbc': 'C4',

        'KN': 'C5',

        'CaRT': 'C3',
        'ILOT': 'C6',
        'PISN': 'C8',
        'TDE': 'C7',

        'FELT': 'C5',
        'Peculiar': 'C5',
    }

    if idx3 is not None:
        if ax is not None:
            raise Exception("Can't make 3D plot with prespecified axis.")

        fig = plt.figure(figsize=(8, 8), constrained_layout=True)

        gs = GridSpec(2, 2, figure=fig)

        ax12 = fig.add_subplot(gs[1, 0])
        ax13 = fig.add_subplot(gs[0, 0], sharex=ax12)
        ax32 = fig.add_subplot(gs[1, 1], sharey=ax12)
        legend_ax = fig.add_subplot(gs[0, 1])
        legend_ax.axis('off')

        plot_vals = [
            (idx1, idx2, ax12),
            (idx1, idx3, ax13),
            (idx3, idx2, ax32),
        ]
    else:
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 6), constrained_layout=True)

        plot_vals = [
            (idx1, idx2, ax)
        ]

    for xidx, yidx, ax in plot_vals:
        if mask is not None:
            cut_predictions = predictions[~mask]
            ax.scatter(cut_predictions[f's{xidx}'], cut_predictions[f's{yidx}'],
                       c='k', s=3, alpha=0.1, label='Unknown')
            valid_predictions = predictions[mask]
        else:
            valid_predictions = predictions

        for type_name in plot_labels:
            type_predictions = valid_predictions[valid_predictions['label'] ==
                                                 type_name]

            color = color_map[type_name]

            markers, caps, bars = ax.errorbar(
                type_predictions[f's{xidx}'][:max_count],
                type_predictions[f's{yidx}'][:max_count],
                xerr=type_predictions[f's{xidx}_error'][:max_count],
                yerr=type_predictions[f's{yidx}_error'][:max_count],
                label=type_name,
                fmt='o',
                marker=marker,
                markersize=markersize,
                c=color,
            )

            [bar.set_alpha(0.3) for bar in bars]

    if idx3 is not None:
        ax12.set_xlabel(f'$s_{idx1}$')
        ax12.set_ylabel(f'$s_{idx2}$')
        ax13.set_ylabel(f'$s_{idx3}$')
        ax13.tick_params(labelbottom=False)
        ax32.set_xlabel(f'$s_{idx3}$')
        ax32.tick_params(labelleft=False)

        if show_legend:
            handles, labels = ax12.get_legend_handles_labels()
            legend_ax.legend(handles=handles, labels=labels, loc='center',
                             ncol=legend_ncol)
    else:
        ax.set_xlabel(f'$s_{idx1}$')
        ax.set_ylabel(f'$s_{idx2}$')

        if show_legend:
            ax.legend(ncol=legend_ncol)
