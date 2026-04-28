"""
NEXUS HAPPO Training Script — Main Entry Point.

Trains the 6 cooperative supply-chain agents using HAPPO
(Heterogeneous-Agent Proximal Policy Optimization) on a single GPU.

Usage
-----
    py -m nexus.training.train --iterations 500 --device cuda
    py -m nexus.training.train --iterations 100 --device cpu --rollout-steps 512
    py -m nexus.training.train --iterations 200 --device cuda --wandb-project nexus-marl

Hardware Requirement
--------------------
Minimum: 8 GB VRAM (RTX 5050 or equivalent).
Estimated VRAM usage: ~900 MB.
Estimated training time: 2-4 hours for 2000 iterations on RTX 5050.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train NEXUS MARL agents with HAPPO",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--iterations", type=int, default=500,
        help="Number of training iterations",
    )
    p.add_argument(
        "--rollout-steps", type=int, default=2048,
        help="Steps per rollout before update",
    )
    p.add_argument(
        "--batch-size", type=int, default=256,
        help="Minibatch size for SGD",
    )
    p.add_argument(
        "--update-epochs", type=int, default=4,
        help="PPO update epochs per iteration",
    )
    p.add_argument(
        "--lr-actor", type=float, default=5e-5,
        help="Actor learning rate (lower for HAPPO multi-agent stability)",
    )
    p.add_argument(
        "--lr-critic", type=float, default=1e-3,
        help="Critic learning rate",
    )
    p.add_argument(
        "--gamma", type=float, default=0.99,
        help="Discount factor",
    )
    p.add_argument(
        "--gae-lambda", type=float, default=0.95,
        help="GAE lambda",
    )
    p.add_argument(
        "--clip-eps", type=float, default=0.2,
        help="PPO clip epsilon",
    )
    p.add_argument(
        "--entropy-coef", type=float, default=0.01,
        help="Entropy bonus coefficient",
    )
    p.add_argument(
        "--device", type=str, default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Training device",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        help="Random seed",
    )
    p.add_argument(
        "--checkpoint-dir", type=str, default="checkpoints",
        help="Directory for saving checkpoints",
    )
    p.add_argument(
        "--log-interval", type=int, default=1,
        help="Log metrics every N iterations",
    )
    p.add_argument(
        "--save-interval", type=int, default=100,
        help="Save checkpoint every N iterations",
    )
    p.add_argument(
        "--max-steps", type=int, default=168,
        help="Episode length (simulated hours)",
    )
    p.add_argument(
        "--disruption-prob", type=float, default=0.02,
        help="Base disruption probability per step",
    )
    # ── Weights & Biases ──────────────────────────────────────
    p.add_argument(
        "--wandb-project", type=str, default=None,
        help="W&B project name (set to enable logging)",
    )
    p.add_argument(
        "--wandb-entity", type=str, default=None,
        help="W&B team/entity name",
    )
    p.add_argument(
        "--wandb-run-name", type=str, default=None,
        help="W&B run name (auto-generated if not set)",
    )
    return p.parse_args()


def setup_logging() -> None:
    """Configure logging with timestamps."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-35s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def detect_device(preference: str) -> str:
    """Auto-detect the best available device."""
    import torch
    if preference == "cuda" or (preference == "auto" and torch.cuda.is_available()):
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            logging.getLogger(__name__).info(
                "Using GPU: %s (%.1f GB VRAM)", name, vram
            )
            return "cuda"
    logging.getLogger(__name__).info("Using CPU")
    return "cpu"


def main():
    args = parse_args()
    setup_logging()
    logger = logging.getLogger("nexus.training")

    # ── Import heavy modules after arg parsing ─────────────────
    import torch
    from nexus.environment.supply_chain_env import SupplyChainEnv
    from nexus.training.happo_trainer import HAPPOTrainer

    # ── Device ─────────────────────────────────────────────────
    device = detect_device(args.device)

    # ── Seed ───────────────────────────────────────────────────
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if device == "cuda":
        torch.cuda.manual_seed(args.seed)

    # ── Environment ────────────────────────────────────────────
    logger.info("Creating SupplyChainEnv (max_steps=%d, p=%.3f)",
                args.max_steps, args.disruption_prob)
    env = SupplyChainEnv(
        render_mode=None,
        max_steps=args.max_steps,
        disruption_probability=args.disruption_prob,
        seed=args.seed,
    )
    obs, infos = env.reset()
    logger.info(
        "Environment ready: %d agents, %d nodes, %d edges",
        len(env.possible_agents),
        env.network.num_nodes,
        env.network.num_edges,
    )

    # ── Print observation / action space summary ───────────────
    for agent_name in env.possible_agents:
        obs_space = env.observation_space(agent_name)
        act_space = env.action_space(agent_name)
        obs_dim = sum(
            int(np.prod(box.shape)) for box in obs_space.spaces.values()
        )
        act_dim = sum(
            int(np.prod(box.shape)) for box in act_space.spaces.values()
        )
        logger.info(
            "  %-12s obs_dim=%-4d act_dim=%-3d",
            agent_name.upper(), obs_dim, act_dim,
        )

    # ── Trainer ────────────────────────────────────────────────
    trainer = HAPPOTrainer(
        env=env,
        lr_actor=args.lr_actor,
        lr_critic=args.lr_critic,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_eps=args.clip_eps,
        entropy_coef=args.entropy_coef,
        update_epochs=args.update_epochs,
        batch_size=args.batch_size,
        rollout_steps=args.rollout_steps,
        device=device,
        checkpoint_dir=args.checkpoint_dir,
    )

    # ── VRAM Report ────────────────────────────────────────────
    if device == "cuda":
        total_params = sum(
            sum(p.numel() for p in actor.parameters())
            for actor in trainer.actors.values()
        )
        total_params += sum(
            p.numel() for p in trainer.critic.parameters()
        )
        logger.info(
            "Total parameters: %s (%.2f MB)",
            f"{total_params:,}", total_params * 4 / 1e6,
        )
        alloc = torch.cuda.memory_allocated() / 1e6
        logger.info("VRAM allocated: %.1f MB", alloc)

    # ── Weights & Biases ───────────────────────────────────────
    wandb_run = None
    if args.wandb_project:
        try:
            import wandb
            wandb_run = wandb.init(
                project=args.wandb_project,
                entity=args.wandb_entity,
                name=args.wandb_run_name,
                config={
                    "algorithm": "HAPPO",
                    "iterations": args.iterations,
                    "rollout_steps": args.rollout_steps,
                    "batch_size": args.batch_size,
                    "update_epochs": args.update_epochs,
                    "lr_actor": args.lr_actor,
                    "lr_critic": args.lr_critic,
                    "gamma": args.gamma,
                    "gae_lambda": args.gae_lambda,
                    "clip_eps": args.clip_eps,
                    "entropy_coef": args.entropy_coef,
                    "max_steps": args.max_steps,
                    "disruption_prob": args.disruption_prob,
                    "seed": args.seed,
                    "device": device,
                    "total_params": sum(
                        sum(p.numel() for p in a.parameters())
                        for a in trainer.actors.values()
                    ) + sum(p.numel() for p in trainer.critic.parameters()),
                    "agents": list(env.possible_agents),
                },
                tags=["happo", "nexus", device],
                settings=wandb.Settings(console="off"),
            )
            logger.info("W&B run: %s", wandb_run.url)
        except ImportError:
            logger.warning("wandb not installed — skipping W&B logging")

    # ── Train ──────────────────────────────────────────────────
    logger.info("=" * 64)
    logger.info("  STARTING HAPPO TRAINING")
    logger.info("  Iterations: %d  |  Rollout: %d  |  Batch: %d",
                args.iterations, args.rollout_steps, args.batch_size)
    logger.info("  Device: %s  |  Seed: %d", device, args.seed)
    logger.info("=" * 64)

    t_start = time.time()
    metrics = trainer.train(
        num_iterations=args.iterations,
        log_interval=args.log_interval,
        save_interval=args.save_interval,
        wandb_run=wandb_run,
    )
    t_total = time.time() - t_start

    # ── Final Report ───────────────────────────────────────────
    logger.info("=" * 64)
    logger.info("  TRAINING COMPLETE")
    logger.info("  Total time: %.1f minutes", t_total / 60)
    logger.info("  Total steps: %s", f"{trainer.total_steps:,}")
    logger.info("  Final mean reward: %.3f",
                metrics[-1]["mean_ep_reward"] if metrics else 0)
    logger.info("=" * 64)

    # ── Save metrics to JSON ───────────────────────────────────
    metrics_path = Path(args.checkpoint_dir) / "training_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert numpy types to Python types for JSON serialization
    clean_metrics = []
    for m in metrics:
        clean = {}
        for k, v in m.items():
            if isinstance(v, (np.floating, np.integer)):
                clean[k] = float(v)
            else:
                clean[k] = v
        clean_metrics.append(clean)

    with open(metrics_path, "w") as f:
        json.dump(clean_metrics, f, indent=2)

    # ── Finish W&B ─────────────────────────────────────────────
    if wandb_run:
        import wandb
        # Log final checkpoint as artifact
        final_ckpt = Path(args.checkpoint_dir) / "nexus_happo_final.pt"
        if final_ckpt.exists():
            artifact = wandb.Artifact("nexus-happo-model", type="model")
            artifact.add_file(str(final_ckpt))
            wandb_run.log_artifact(artifact)
            logger.info("Model artifact uploaded to W&B")
        wandb_run.finish()
        logger.info("W&B run finished")
    logger.info("Metrics saved to %s", metrics_path)


if __name__ == "__main__":
    main()
