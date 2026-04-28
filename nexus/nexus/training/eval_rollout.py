"""
Evaluation rollout — compare trained HAPPO agents vs heuristic baseline.

Runs both the trained RL policies and the hand-crafted SENTINEL heuristic
against a suite of crisis scenarios and reports comparative metrics:
  • Green-Resilience Score (GRS)
  • SLA compliance rate
  • Mean disruption response time
  • Total delay hours
  • Shipments delivered

Usage
-----
    py -m nexus.training.eval_rollout --checkpoint checkpoints/nexus_happo_final.pt
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate trained NEXUS agents vs heuristic baseline",
    )
    p.add_argument(
        "--checkpoint", type=str, required=True,
        help="Path to trained HAPPO checkpoint (.pt file)",
    )
    p.add_argument(
        "--episodes", type=int, default=20,
        help="Number of evaluation episodes",
    )
    p.add_argument(
        "--device", type=str, default="cpu",
        help="Device for inference",
    )
    p.add_argument(
        "--seed", type=int, default=123,
        help="Evaluation seed",
    )
    p.add_argument(
        "--max-steps", type=int, default=168,
        help="Episode length",
    )
    return p.parse_args()


def run_heuristic_episode(env, seed: int) -> dict:
    """
    Run one episode with the hand-crafted heuristic policies.

    Each agent uses simple rule-based logic:
      SENTINEL: risk = 0.5 * weather + 0.3 * congestion + 0.2 * disruption
      NAVIGATOR: reroute if at-risk > 0.5
      GUARDIAN: open circuit if health < 0.35
      STOCKPILE: pre-position if risk > 0.5
      BROKER: blackout if health < 0.4
      HERALD: alert if SLA breach prob > 0.5
    """
    obs, infos = env.reset(seed=seed)
    total_reward = 0.0
    step = 0

    while env.agents:
        actions = {}
        for agent_name in env.agents:
            act_space = env.action_space(agent_name)
            action = {}
            for key, box in act_space.spaces.items():
                if agent_name == "sentinel" and key == "risk_scores":
                    # Simple weighted fusion
                    w = obs[agent_name].get("weather_severity", np.zeros(15))
                    c = obs[agent_name].get("congestion_scores", np.zeros(15))
                    d = obs[agent_name].get("disruption_active", np.zeros(15))
                    risk = np.clip(0.5 * w / 10 + 0.3 * c + 0.2 * d, 0, 1)
                    action[key] = risk.astype(np.float32)
                elif agent_name == "guardian" and key == "circuit_actions":
                    # Open if health < 0.35
                    health = obs[agent_name].get(
                        "node_health", np.ones(15)
                    )
                    acts = np.where(health < 0.35, 0.5, 0.1)
                    action[key] = acts.astype(np.float32)
                elif agent_name == "navigator" and key == "reroute_flags":
                    at_risk = obs[agent_name].get(
                        "shipment_at_risk", np.zeros(30)
                    )
                    action[key] = (at_risk > 0.5).astype(np.float32)
                elif agent_name == "stockpile" and key == "transfer_triggers":
                    risk = obs[agent_name].get(
                        "risk_scores", np.zeros(15)
                    )
                    action[key] = (risk > 0.5).astype(np.float32)
                elif agent_name == "broker" and key == "carrier_flags":
                    health = obs[agent_name].get(
                        "carrier_health", np.ones(8)
                    )
                    action[key] = np.where(
                        health < 0.4, 0.2, 0.8
                    ).astype(np.float32)
                elif agent_name == "herald" and key == "alert_priorities":
                    breach = obs[agent_name].get(
                        "sla_breach_probability", np.zeros(30)
                    )
                    action[key] = (breach > 0.5).astype(np.float32)
                else:
                    action[key] = np.ones(box.shape, dtype=np.float32) * 0.5
            actions[agent_name] = action

        obs, rewards, terms, truncs, infos = env.step(actions)
        if rewards:
            total_reward += sum(rewards.values())
        step += 1

    state = env.get_state()
    metrics = state["metrics"]
    return {
        "total_reward": total_reward,
        "steps": step,
        "delivered": metrics["shipments_delivered"],
        "sla_breaches": metrics["sla_breaches"],
        "total_delay_hours": metrics["total_delay_hours"],
        "disruptions": metrics["total_disruptions"],
        "reroutes": metrics["reroutes"],
        "circuit_opens": metrics["circuit_opens"],
    }


def run_trained_episode(env, trainer, seed: int) -> dict:
    """
    Run one episode with trained HAPPO policies.
    """
    import torch
    from nexus.training.networks import _flatten_obs

    obs, infos = env.reset(seed=seed)
    total_reward = 0.0
    step = 0

    while env.agents:
        actions = {}
        for agent_name in env.agents:
            obs_flat = _flatten_obs(obs[agent_name]).to(trainer.device)
            with torch.no_grad():
                action, _ = trainer.actors[agent_name].get_action(
                    obs_flat, deterministic=True
                )
            action_np = action.cpu().numpy()
            actions[agent_name] = trainer._unflatten_action(
                agent_name, action_np
            )

        obs, rewards, terms, truncs, infos = env.step(actions)
        if rewards:
            total_reward += sum(rewards.values())
        step += 1

    state = env.get_state()
    metrics = state["metrics"]
    return {
        "total_reward": total_reward,
        "steps": step,
        "delivered": metrics["shipments_delivered"],
        "sla_breaches": metrics["sla_breaches"],
        "total_delay_hours": metrics["total_delay_hours"],
        "disruptions": metrics["total_disruptions"],
        "reroutes": metrics["reroutes"],
        "circuit_opens": metrics["circuit_opens"],
    }


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("eval")

    import torch
    from nexus.environment.supply_chain_env import SupplyChainEnv
    from nexus.training.happo_trainer import HAPPOTrainer

    # ── Create env ─────────────────────────────────────────────
    env = SupplyChainEnv(
        max_steps=args.max_steps,
        disruption_probability=0.03,
        seed=args.seed,
    )
    env.reset()

    # ── Load trained model ─────────────────────────────────────
    trainer = HAPPOTrainer(
        env=env,
        device=args.device,
        checkpoint_dir="eval_tmp",
    )
    trainer.load_checkpoint(args.checkpoint)
    logger.info("Loaded checkpoint: %s", args.checkpoint)

    # ── Run episodes ───────────────────────────────────────────
    heuristic_results = []
    trained_results = []

    for ep in range(args.episodes):
        ep_seed = args.seed + ep

        h_result = run_heuristic_episode(env, ep_seed)
        heuristic_results.append(h_result)

        t_result = run_trained_episode(env, trainer, ep_seed)
        trained_results.append(t_result)

        logger.info(
            "Episode %2d | Heuristic: reward=%+7.1f del=%2d sla=%d | "
            "Trained: reward=%+7.1f del=%2d sla=%d",
            ep + 1,
            h_result["total_reward"], h_result["delivered"],
            h_result["sla_breaches"],
            t_result["total_reward"], t_result["delivered"],
            t_result["sla_breaches"],
        )

    # ── Aggregate ──────────────────────────────────────────────
    def avg(results, key):
        return np.mean([r[key] for r in results])

    print("\n" + "=" * 70)
    print("  NEXUS EVALUATION REPORT")
    print("=" * 70)
    print(f"  Episodes: {args.episodes}  |  "
          f"Disruption Rate: 3%  |  Steps: {args.max_steps}")
    print("-" * 70)
    print(f"  {'Metric':<30s}  {'Heuristic':>12s}  {'HAPPO':>12s}  {'Δ':>10s}")
    print("-" * 70)

    keys = [
        ("total_reward", "Total Reward"),
        ("delivered", "Shipments Delivered"),
        ("sla_breaches", "SLA Breaches"),
        ("total_delay_hours", "Total Delay (hours)"),
        ("reroutes", "Reroutes"),
        ("circuit_opens", "Circuit Opens"),
    ]

    for key, label in keys:
        h = avg(heuristic_results, key)
        t = avg(trained_results, key)
        delta = t - h
        better = "↓" if key in ["sla_breaches", "total_delay_hours"] else "↑"
        print(f"  {label:<30s}  {h:>12.1f}  {t:>12.1f}  {delta:>+9.1f} {better}")

    print("=" * 70)

    # ── Save to JSON ───────────────────────────────────────────
    report = {
        "episodes": args.episodes,
        "checkpoint": args.checkpoint,
        "heuristic": {k: float(avg(heuristic_results, k)) for k, _ in keys},
        "trained": {k: float(avg(trained_results, k)) for k, _ in keys},
    }
    out = Path(args.checkpoint).parent / "eval_report.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Report saved to %s", out)


if __name__ == "__main__":
    main()
