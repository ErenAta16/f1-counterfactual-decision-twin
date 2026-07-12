"""A conjugate Bayesian linear model for tyre-compound pace degradation.

The model is deliberately simple: linear-in-tyre-life degradation per
compound, fit with a Normal-Inverse-Gamma conjugate prior so the posterior
and posterior predictive distribution are both closed-form. This keeps the
implementation auditable without adding a sampling-based modelling
dependency before Phase 2's exit criterion (calibrated intervals, at least
matching the naive baseline) is known to be reachable at all.

The predictive distribution is technically Student-t; with the lap counts
available in this dataset the degrees of freedom run into the hundreds, so
the Normal approximation used below differs from the exact predictive
variance by a negligible amount. This is noted rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


class PaceModelError(ValueError):
    """Raised when the pace model cannot be fit or queried."""


@dataclass(frozen=True)
class PacePosterior:
    """Closed-form Normal-Inverse-Gamma posterior over pace-model coefficients."""

    feature_names: tuple[str, ...]
    coefficient_mean: np.ndarray
    coefficient_covariance: np.ndarray
    shape: float
    scale: float
    observation_count: int

    @property
    def noise_variance_mean(self) -> float:
        """Posterior mean of the residual noise variance, E[sigma^2] = b/(a-1)."""

        if self.shape <= 1:
            raise PaceModelError("Shape parameter too small for a defined noise-variance mean.")
        return self.scale / (self.shape - 1)


def fit_bayesian_pace_model(
    design: pd.DataFrame,
    target: pd.Series,
    *,
    prior_scale: float = 5.0,
    prior_shape: float = 2.0,
    prior_rate: float = 1.0,
) -> PacePosterior:
    """Fit the conjugate Normal-Inverse-Gamma pace model.

    ``prior_scale`` sets the prior standard deviation on every coefficient
    (weakly informative: wide enough that the data dominates quickly, but
    centred on zero so a compound with no supporting laps predicts no
    offset and no degradation rather than extrapolating from nothing).
    """

    if design.empty or len(design) != len(target):
        raise PaceModelError("Design matrix and target must be non-empty and aligned.")
    if prior_scale <= 0:
        raise PaceModelError("prior_scale must be positive.")

    x = design.to_numpy(dtype=float)
    y = target.to_numpy(dtype=float)
    n, p = x.shape

    prior_precision = np.eye(p) / (prior_scale**2)
    posterior_precision = prior_precision + x.T @ x
    posterior_covariance = np.linalg.inv(posterior_precision)
    posterior_mean = posterior_covariance @ (x.T @ y)

    posterior_shape = prior_shape + n / 2
    residual_term = y @ (y - x @ posterior_mean)
    posterior_rate = prior_rate + 0.5 * residual_term

    return PacePosterior(
        feature_names=tuple(design.columns),
        coefficient_mean=posterior_mean,
        coefficient_covariance=posterior_covariance,
        shape=posterior_shape,
        scale=posterior_rate,
        observation_count=n,
    )


def predict(posterior: PacePosterior, design: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return the predictive mean and variance for each row of ``design``.

    Predictive variance combines residual noise (``scale / shape``) with
    parameter uncertainty (``x' V x``), so rows that resemble little of the
    training data get a wider, more honest interval instead of a falsely
    confident point estimate.
    """

    if list(design.columns) != list(posterior.feature_names):
        raise PaceModelError("Design columns do not match the columns the model was fit on.")

    x = design.to_numpy(dtype=float)
    mean = x @ posterior.coefficient_mean
    noise_scale = posterior.scale / posterior.shape
    parameter_variance = np.einsum("ij,jk,ik->i", x, posterior.coefficient_covariance, x)
    variance = noise_scale * (1.0 + parameter_variance)
    return mean, variance
