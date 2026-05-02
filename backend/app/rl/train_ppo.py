from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from ..config import EMS_DATASET, OUTPUT_DIR, PLOTS_DIR, PPO_MODEL_DIR, ensure_project_dirs
from ..gpu import require_cuda_device
from ..utils import write_json
from .microgrid_env import MicrogridPPOEnv


class RewardTraceCallback(BaseCallback):
    def __init__(self) -> None:
        super().__init__()
        self.rewards: list[float] = []

    def _on_step(self) -> bool:
        reward = self.locals.get("rewards")
        if reward is not None:
            self.rewards.append(float(reward[0]))
        return True


def train_ppo(total_timesteps: int = 80_000) -> dict[str, object]:
    ensure_project_dirs()
    require_cuda_device()
    if not EMS_DATASET.exists():
        from ..data.synthetic import generate_operational_dataset

        generate_operational_dataset()

    env = DummyVecEnv([lambda: Monitor(MicrogridPPOEnv(EMS_DATASET))])
    callback = RewardTraceCallback()
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=256,
        gamma=0.99,
        gae_lambda=0.95,
        ent_coef=0.01,
        clip_range=0.2,
        verbose=1,
        device="cuda",
        seed=42,
    )
    model.learn(total_timesteps=total_timesteps, callback=callback)
    model_path = PPO_MODEL_DIR / "microgrid_ppo"
    model.save(str(model_path))

    reward_df = pd.DataFrame({"step": range(len(callback.rewards)), "reward": callback.rewards})
    reward_df["rolling_reward"] = reward_df["reward"].rolling(250, min_periods=1).mean()
    reward_df.to_csv(OUTPUT_DIR / "ppo_reward_trace.csv", index=False)
    _plot_rewards(reward_df)
    action_df = sample_actions(model, steps=24 * 14)
    _plot_actions(action_df)
    report = {
        "model_path": str(model_path) + ".zip",
        "total_timesteps": total_timesteps,
        "reward_trace_csv": str(OUTPUT_DIR / "ppo_reward_trace.csv"),
        "action_sample_csv": str(OUTPUT_DIR / "ppo_action_samples.csv"),
        "reward_plot": str(PLOTS_DIR / "ppo_reward_curve.png"),
        "action_plot": str(PLOTS_DIR / "ppo_action_patterns.png"),
    }
    write_json(OUTPUT_DIR / "ppo_training_report.json", report)
    return report


def sample_actions(model: PPO, steps: int = 336) -> pd.DataFrame:
    env = MicrogridPPOEnv(EMS_DATASET, episode_length=steps)
    obs, _ = env.reset(seed=42)
    records = []
    for _ in range(steps):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(int(action))
        records.append({"reward": reward, **info})
        if terminated or truncated:
            break
    action_df = pd.DataFrame(records)
    action_df.to_csv(OUTPUT_DIR / "ppo_action_samples.csv", index=False)
    return action_df


def _plot_rewards(reward_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(reward_df["step"], reward_df["rolling_reward"], color="#0f766e")
    ax.set_title("PPO Reward Curve - Rolling Mean")
    ax.set_xlabel("Training step")
    ax.set_ylabel("Reward")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "ppo_reward_curve.png", dpi=150)
    plt.close(fig)


def _plot_actions(action_df: pd.DataFrame) -> None:
    counts = action_df["action_name"].value_counts().reindex(["idle", "charge", "discharge"]).fillna(0)
    fig, ax = plt.subplots(figsize=(8, 5))
    counts.plot(kind="bar", ax=ax, color=["#495057", "#2f9e44", "#1971c2"])
    ax.set_title("PPO Action Pattern Sample")
    ax.set_ylabel("Action count")
    ax.set_xlabel("Action")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "ppo_action_patterns.png", dpi=150)
    plt.close(fig)

