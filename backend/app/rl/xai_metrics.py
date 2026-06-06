from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from stable_baselines3 import PPO


def calculate_decision_entropy(std: float | np.ndarray) -> float | np.ndarray:
    """
    Compute Decision Entropy for a Gaussian policy: H = 0.5 * ln(2 * pi * e * std^2).
    """
    if isinstance(std, np.ndarray):
        return 0.5 * np.log(2.0 * np.pi * np.e * (std ** 2) + 1e-6)
    return float(0.5 * np.log(2.0 * np.pi * np.e * (std ** 2) + 1e-6))


def calculate_integrated_gradients(
    ppo_model: PPO,
    state: np.ndarray,
    baseline_state: np.ndarray | None = None,
    steps: int = 30
) -> np.ndarray:
    """
    Compute Integrated Gradients attribution for the PPO continuous policy network.
    """
    if baseline_state is None:
        # Default baseline: BESS at 50% SoC, zero solar/wind, 50% load, weekend/weekday at 0
        baseline_state = np.array([0.0, 0.0, 0.2, 0.5, 1.0, 0.2, 0.5, 0.5, 0.0], dtype=np.float32)

    device = ppo_model.device
    policy = ppo_model.policy.to(device)
    policy.eval()

    # Convert to PyTorch tensors
    state_t = torch.tensor(state, dtype=torch.float32, device=device)
    baseline_t = torch.tensor(baseline_state, dtype=torch.float32, device=device)

    # Accumulator for gradients
    grads = torch.zeros_like(state_t)

    # Linear interpolation path
    for k in range(1, steps + 1):
        alpha = k / steps
        interpolated = baseline_t + alpha * (state_t - baseline_t)
        interpolated = interpolated.clone().detach().requires_grad_(True)
        
        # Forward pass to get action mean (continuous action)
        # Note: SB3 continuous policies output a distribution from which we can extract the mean
        latent_pi, _, _ = policy.features_extractor(interpolated.unsqueeze(0)), None, None
        if hasattr(policy, "mlp_extractor"):
            latent_pi, _ = policy.mlp_extractor(interpolated.unsqueeze(0))
        mean_action = policy.action_net(latent_pi)

        # Backward pass
        mean_action.backward()
        
        if interpolated.grad is not None:
            grads += interpolated.grad.squeeze(0)

    # Integrated Gradients formula
    ig = (state_t - baseline_t) * (grads / steps)
    return ig.cpu().detach().numpy()


def calculate_explanation_fidelity(
    drl_actions: np.ndarray,
    rule_actions: np.ndarray
) -> float:
    """
    Fidelity is the agreement rate between DRL actions and rule-based heuristic directions.
    """
    # Sign of actions: charge (<0), discharge (>0), idle (0)
    drl_sign = np.sign(drl_actions)
    rule_sign = np.sign(rule_actions)
    
    # Sign mapping: charge is -1, discharge is 1, idle is 0
    # Map values within epsilon
    drl_sign[np.abs(drl_actions) <= 0.5] = 0
    rule_sign[np.abs(rule_actions) <= 0.5] = 0
    
    return float(np.mean(drl_sign == rule_sign))


def calculate_attribution_stability(
    ppo_model: PPO,
    state: np.ndarray,
    ig_nominal: np.ndarray,
    perturbation_scale: float = 0.01,
    num_samples: int = 10
) -> float:
    """
    Attribution stability: measures the change in Integrated Gradients under input noise.
    """
    stabilities = []
    for _ in range(num_samples):
        # Add Gaussian noise
        noise = np.random.normal(0, perturbation_scale, size=state.shape).astype(np.float32)
        perturbed_state = np.clip(state + noise, 0.0, 1.0)
        
        ig_perturbed = calculate_integrated_gradients(ppo_model, perturbed_state)
        
        l1_diff = np.sum(np.abs(ig_perturbed - ig_nominal))
        l1_norm = np.sum(np.abs(ig_nominal)) + 1e-6
        
        stabilities.append(1.0 - (l1_diff / l1_norm))
        
    return float(np.mean(stabilities))
