"""
Plotting functions are implemented here and also monkeypatched into
the DataArray class
"""

import functools

import numpy as np

from .utils import is_uniform_spaced

# TODO - Is there a better way to import matplotlib in the function?
# Other piece of duplicated logic is the checking for axes.
# Decorators don't preserve the argument names
# But if all the plotting methods have same signature...


# TODO - implement this
class FacetGrid():
    pass


def _ensure_plottable(*args):
    """
    Raise exception if there is anything in args that can't be plotted on
    an axis.
    """
    plottypes = [np.floating, np.integer, np.timedelta64, np.datetime64]

    righttype = lambda x: any(np.issubdtype(x.dtype, t) for t in plottypes)

    # Lists need to be converted to np.arrays here.
    if not any(righttype(np.array(x)) for x in args):
        raise TypeError('Plotting requires coordinates to be numeric '
                        'or dates. Try DataArray.reindex() to convert.')


def plot(darray, ax=None, rtol=0.01, **kwargs):
    """
    Default plot of DataArray using matplotlib / pylab.

    Calls xray plotting function based on the dimensions of
    the array:

    =============== =========== ===========================
    Dimensions      Coordinates Plotting function
    --------------- ----------- ---------------------------
    1                           :py:meth:`xray.DataArray.plot_line`
    2               Uniform     :py:meth:`xray.DataArray.plot_imshow`
    2               Irregular   :py:meth:`xray.DataArray.plot_contourf`
    Anything else               :py:meth:`xray.DataArray.plot_hist`
    =============== =========== ===========================

    Parameters
    ----------
    darray : DataArray
    ax : matplotlib axes object
        If None, uses the current axis
    rtol : relative tolerance
        Relative tolerance used to determine if the indexes
        are uniformly spaced
    kwargs
        Additional keyword arguments to matplotlib

    """
    ndims = len(darray.dims)

    if ndims == 1:
        plotfunc = plot_line
    elif ndims == 2:
        indexes = darray.indexes.values()
        if all(is_uniform_spaced(i, rtol=rtol) for i in indexes):
            plotfunc = plot_imshow
        else:
            plotfunc = plot_contourf
    else:
        plotfunc = plot_hist

    kwargs['ax'] = ax
    return plotfunc(darray, **kwargs)


# This function signature should not change so that it can use
# matplotlib format strings
def plot_line(darray, *args, **kwargs):
    """
    Line plot of 1 dimensional DataArray index against values

    Wraps matplotlib.pyplot.plot

    Parameters
    ----------
    darray : DataArray
        Must be 1 dimensional
    ax : matplotlib axes object
        If not passed, uses the current axis
    args, kwargs
        Additional arguments to matplotlib.pyplot.plot

    """
    import matplotlib.pyplot as plt

    ndims = len(darray.dims)
    if ndims != 1:
        raise ValueError('Line plots are for 1 dimensional DataArrays. '
                         'Passed DataArray has {} dimensions'.format(ndims))

    # Ensures consistency with .plot method
    ax = kwargs.pop('ax', None)

    if ax is None:
        ax = plt.gca()

    xlabel, x = list(darray.indexes.items())[0]

    _ensure_plottable([x])

    primitive = ax.plot(x, darray, *args, **kwargs)

    ax.set_xlabel(xlabel)

    if darray.name is not None:
        ax.set_ylabel(darray.name)

    return primitive


def plot_hist(darray, ax=None, **kwargs):
    """
    Histogram of DataArray

    Wraps matplotlib.pyplot.hist

    Plots N dimensional arrays by first flattening the array.

    Parameters
    ----------
    darray : DataArray
        Can be any dimension
    ax : matplotlib axes object
        If not passed, uses the current axis
    kwargs :
        Additional keyword arguments to matplotlib.pyplot.hist

    """
    import matplotlib.pyplot as plt

    if ax is None:
        ax = plt.gca()

    no_nan = np.ravel(darray)
    no_nan = no_nan[np.logical_not(np.isnan(no_nan))]
    primitive = ax.hist(no_nan, **kwargs)

    ax.set_ylabel('Count')

    if darray.name is not None:
        ax.set_title('Histogram of {}'.format(darray.name))

    return primitive


def _update_axes_limits(ax, xincrease, yincrease):
    """
    Update axes in place to increase or decrease
    For use in _plot2d
    """
    if xincrease is None:
        pass
    elif xincrease:
        ax.set_xlim(sorted(ax.get_xlim()))
    elif not xincrease:
        ax.set_xlim(sorted(ax.get_xlim(), reverse=True))

    if yincrease is None:
        pass
    elif yincrease:
        ax.set_ylim(sorted(ax.get_ylim()))
    elif not yincrease:
        ax.set_ylim(sorted(ax.get_ylim(), reverse=True))


def _plot2d(plotfunc):
    """
    Decorator for common 2d plotting logic. 
    """
    commondoc = '''
    Parameters
    ----------
    darray : DataArray
        Must be 2 dimensional
    ax : matplotlib axes object
        If None, uses the current axis
    xincrease : None (default), True, or False
        Should the values on the x axes be increasing from left to right?
        if None, use the default for the matplotlib function
    yincrease : None (default), True, or False
        Should the values on the y axes be increasing from top to bottom?
        if None, use the default for the matplotlib function
    add_colorbar : Boolean
        Adds colorbar to axis
    kwargs :
        Additional arguments to wrapped matplotlib function

    Returns
    -------
    artist :
        The same type of primitive artist that the wrapped matplotlib 
        function returns
    '''

    # Build on the original docstring
    plotfunc.__doc__ = '\n'.join((plotfunc.__doc__, commondoc))

    @functools.wraps(plotfunc)
    def wrapper(darray, ax=None, xincrease=None, yincrease=None, add_colorbar=True, **kwargs):
        # All 2d plots in xray share this function signature

        import matplotlib.pyplot as plt

        if ax is None:
            ax = plt.gca()

        try:
            ylab, xlab = darray.dims
        except ValueError:
            raise ValueError('{} plots are for 2 dimensional DataArrays. '
                             'Passed DataArray has {} dimensions'
                             .format(plotfunc.__name__, len(darray.dims)))

        x = darray[xlab]
        y = darray[ylab]
        z = darray

        _ensure_plottable(x, y)

        ax, primitive = plotfunc(x, y, z, ax=ax, **kwargs)

        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)

        if add_colorbar:
            plt.colorbar(primitive, ax=ax)

        _update_axes_limits(ax, xincrease, yincrease)

        return primitive
    return wrapper


@_plot2d
def plot_imshow(x, y, z, ax, **kwargs):
    """
    Image plot of 2d DataArray using matplotlib / pylab

    Wraps matplotlib.pyplot.imshow

    ..warning::
        This function needs uniformly spaced coordinates to
        properly label the axes. Call DataArray.plot() to check.

    The pixels are centered on the coordinates values. Ie, if the coordinate
    value is 3.2 then the pixels for those coordinates will be centered on 3.2.
    """
    # Centering the pixels- Assumes uniform spacing
    xstep = (x[1] - x[0]) / 2.0
    ystep = (y[1] - y[0]) / 2.0
    left, right = x[0] - xstep, x[-1] + xstep
    bottom, top = y[-1] + ystep, y[0] - ystep

    defaults = {'extent': [left, right, bottom, top],
                'aspect': 'auto',
                'interpolation': 'nearest',
                }

    # Allow user to override these defaults
    defaults.update(kwargs)

    primitive = ax.imshow(z, **defaults)

    return ax, primitive


@_plot2d
def plot_contourf(x, y, z, ax, **kwargs):
    """
    Filled contour plot of 2d DataArray

    Wraps matplotlib.pyplot.contourf
    """
    primitive = ax.contourf(x, y, z, **kwargs)
    return ax, primitive
