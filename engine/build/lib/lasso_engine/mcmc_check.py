"""Validate the Laplace posterior against full Bayesian inference (NUTS).

    python -m lasso_engine.mcmc_check --data ../data/league --out ../data/model

1. Same model, same fixed priors: NUTS vs Laplace means and standard deviations.
2. Fully hierarchical model (sigma_att, sigma_def learned): the posterior for
   the prior widths, checking the tuned values are consistent with the data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import numpyro
import numpyro.distributions as dist
import pandas as pd
from numpyro.infer import MCMC, NUTS

from .strength import StrengthHyper, fit_strength, global_matchday

numpyro.set_host_device_count(1)


def _arrays(matches: pd.DataFrame, clubs: list[str]):
    idx = {c: i for i, c in enumerate(clubs)}
    return (jnp.array(matches.home_id.map(idx).to_numpy()), jnp.array(matches.away_id.map(idx).to_numpy()),
            jnp.array(matches.home_xg.to_numpy()), jnp.array(matches.away_xg.to_numpy()))


def model(hi, ai, ch, ca, n, sigma_att=None, sigma_def=None):
    mu = numpyro.sample("mu", dist.Normal(0.2, 1.0))
    home = numpyro.sample("home", dist.Normal(0.2, 0.2))
    s_att = sigma_att if sigma_att is not None else numpyro.sample("sigma_att", dist.HalfNormal(0.5))
    s_def = sigma_def if sigma_def is not None else numpyro.sample("sigma_def", dist.HalfNormal(0.5))
    att = numpyro.sample("att", dist.Normal(0, s_att).expand([n]))
    dfn = numpyro.sample("def", dist.Normal(0, s_def).expand([n]))
    lh = jnp.exp(mu + home + att[hi] - dfn[ai])
    la = jnp.exp(mu + att[ai] - dfn[hi])
    # Poisson quasi-likelihood on (non-integer) xG counts.
    numpyro.factor("lik", jnp.sum(ch * jnp.log(lh) - lh) + jnp.sum(ca * jnp.log(la) - la))


def run(m, *a, **kw):
    mc = MCMC(NUTS(m), num_warmup=800, num_samples=1500, num_chains=1, progress_bar=False)
    mc.run(jax.random.PRNGKey(0), *a, **kw)
    return mc.get_samples()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/league")
    ap.add_argument("--out", default="../data/model")
    ap.add_argument("--seasons", default="3,4")
    args = ap.parse_args()
    data = Path(args.data)
    seasons = [int(s) for s in args.seasons.split(",")]
    matches = pd.read_parquet(data / "matches.parquet")
    matches = matches[matches.season.isin(seasons)]
    clubs = sorted(pd.read_parquet(data / "clubs.parquet").club_id)
    n = len(clubs)
    hyper = StrengthHyper(decay_per_matchday=0.0, alpha_goals=0.0)
    as_of = int(global_matchday(max(seasons), 38)) + 1
    lap = fit_strength(matches, clubs, as_of, hyper)

    arrays = _arrays(matches, clubs)
    s = run(model, *arrays, n, sigma_att=hyper.sigma_att, sigma_def=hyper.sigma_def)
    nuts_mean = np.concatenate([[s["mu"].mean(), s["home"].mean()], s["att"].mean(0), s["def"].mean(0)])
    nuts_sd = np.concatenate([[s["mu"].std(), s["home"].std()], s["att"].std(0), s["def"].std(0)])
    lap_sd = lap.sd()
    fixed = {
        "max_abs_mean_diff": float(np.max(np.abs(nuts_mean - lap.mean))),
        "mean_corr": float(np.corrcoef(nuts_mean[2:], lap.mean[2:])[0, 1]),
        "sd_ratio_median": float(np.median(lap_sd / nuts_sd)),
    }
    h = run(model, *arrays, n)
    hier = {
        "sigma_att_median": float(np.median(h["sigma_att"])),
        "sigma_att_90ci": [float(v) for v in np.percentile(h["sigma_att"], [5, 95])],
        "sigma_def_median": float(np.median(h["sigma_def"])),
        "sigma_def_90ci": [float(v) for v in np.percentile(h["sigma_def"], [5, 95])],
        "tuned": {"sigma_att": StrengthHyper().sigma_att, "sigma_def": StrengthHyper().sigma_def},
    }
    out = {"seasons": seasons, "laplace_vs_nuts": fixed, "hierarchical": hier}
    Path(args.out, "mcmc_check.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
