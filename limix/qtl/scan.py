from __future__ import division

from pandas import Series

from glimix_core.glmm import GLMMExpFam, GLMMNormal
from glimix_core.lmm import LMM
from numpy_sugar.linalg import economic_qs

from ..dataframe import normalise_dataset
from .model import QTLModel
from .util import print_analysis


def scan(G, y, lik, K=None, M=None, verbose=True):
    r"""Single-variant association testing via generalised linear mixed models.

    It supports Normal (linear mixed model), Bernoulli, Binomial, and Poisson
    residual errors, defined by ``lik``.
    The columns of ``G`` define the candidates to be tested for association
    with the phenotype ``y``.
    The covariance matrix is set by ``K``.
    If not provided, or set to ``None``, the generalised linear model
    without random effects is assumed.
    The covariates can be set via the parameter ``M``.
    We recommend to always provide a column of ones in the case

    Parameters
    ----------
    G : array_like
        `n` individuals by `s` candidate markers.
    y : tuple, array_like
        Either a tuple of two arrays of `n` individuals each (Binomial
        phenotypes) or an array of `n` individuals (Normal, Poisson, or
        Bernoulli phenotypes). It does not support missing values yet.
    lik : {'normal', 'bernoulli', 'binomial', 'poisson'}
        Sample likelihood describing the residual distribution.
    K : array_like, optional
        `n` by `n` covariance matrix (e.g., kinship coefficients).
        Set to ``None`` for a generalised linear model without random effects.
        Defaults to ``None``.
    M : array_like, optional
        `n` individuals by `d` covariates.
        By default, ``M`` is an `n` by `1` matrix of ones.
    verbose : bool, optional
        if ``True``, details such as runtime are displayed.

    Returns
    -------
    :class:`limix.qtl.model.QTLModel`
        QTL representation.

    Examples
    --------
    .. doctest::

        >>> from numpy import dot, exp, sqrt, ones
        >>> from numpy.random import RandomState
        >>> from pandas import DataFrame
        >>> from limix.qtl import scan
        >>>
        >>> random = RandomState(1)
        >>>
        >>> n = 30
        >>> p = 3
        >>> samples_index = range(n)
        >>>
        >>> M = DataFrame(dict(offset=ones(n), age=random.randint(10, 60, n)))
        >>> M.index = samples_index
        >>>
        >>> X = random.randn(n, 100)
        >>> K = dot(X, X.T)
        >>>
        >>> candidates = random.randn(n, p)
        >>> candidates = DataFrame(candidates, index=samples_index,
        ...                                    columns=['rs0', 'rs1', 'rs2'])
        >>>
        >>> y = random.poisson(exp(random.randn(n)))
        >>>
        >>> model = scan(candidates, y, 'poisson', K, M=M, verbose=False)
        >>>
        >>> model.variant_pvalues  # doctest: +FLOAT_CMP
        rs0    0.554445
        rs1    0.218997
        rs2    0.552201
        dtype: float64
        >>> model.variant_effsizes  # doctest: +FLOAT_CMP
        rs0   -0.130867
        rs1   -0.315078
        rs2   -0.143869
        dtype: float64
        >>> model.variant_effsizes_se  # doctest: +FLOAT_CMP
        rs0    0.221390
        rs1    0.256327
        rs2    0.242014
        dtype: float64
        >>> model  # doctest: +FLOAT_CMP
        Variants
               effsizes  effsizes_se   pvalues
        count  3.000000     3.000000  3.000000
        mean  -0.196604     0.239910  0.441881
        std    0.102807     0.017563  0.193027
        min   -0.315078     0.221390  0.218997
        25%   -0.229473     0.231702  0.385599
        50%   -0.143869     0.242014  0.552201
        75%   -0.137368     0.249171  0.553323
        max   -0.130867     0.256327  0.554445
        <BLANKLINE>
        Covariate effect sizes for the null model
           offset       age
         0.395284 -0.005568
    """
    lik = lik.lower()

    if verbose:
        print_analysis(lik, "Quantitative trait locus analysis")

    data = normalise_dataset(y, lik, M=M, G=G, K=K)
    y = data["y"]
    M = data["M"]
    G = data["G"]
    K = data["K"]

    if K is not None:
        QS = economic_qs(K)
    else:
        QS = None

    if lik == "normal":
        model = _perform_lmm(y.values, M, QS, G, verbose)
    else:
        model = _perform_glmm(y.values, lik, M, K, QS, G, verbose)

    if verbose:
        print(model)

    return model


def _perform_lmm(y, M, QS, G, verbose):
    lmm = LMM(y, M.values, QS)

    lmm.fit(verbose=verbose)

    null_lml = lmm.lml()

    beta = lmm.beta

    keys = list(M.keys())
    ncov_effsizes = Series(beta, keys)

    flmm = lmm.get_fast_scanner()
    alt_lmls, effsizes = flmm.fast_scan(G.values, verbose=verbose)

    alt_lmls = Series(alt_lmls, list(G.columns))
    effsizes = Series(effsizes, list(G.columns))

    return QTLModel(null_lml, alt_lmls, effsizes, ncov_effsizes)


def _perform_glmm(y, lik, M, K, QS, G, verbose):

    glmm = GLMMExpFam(y, lik, M.values, QS)
    glmm.fit(verbose=verbose)

    eta = glmm.site.eta
    tau = glmm.site.tau

    gnormal = GLMMNormal(eta, tau, M.values, QS)
    gnormal.fit(verbose=verbose)

    beta = gnormal.beta

    keys = list(M.keys())
    ncov_effsizes = Series(beta, keys)

    flmm = gnormal.get_fast_scanner()
    flmm.set_scale(1.0)
    null_lml = flmm.null_lml()

    alt_lmls, effsizes = flmm.fast_scan(G.values, verbose=verbose)

    alt_lmls = Series(alt_lmls, list(G.keys()))
    effsizes = Series(effsizes, list(G.keys()))

    return QTLModel(null_lml, alt_lmls, effsizes, ncov_effsizes)
