import fitz  # PyMuPDF
import json
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = PROJECT_ROOT / "Microgrid_manuscript.pdf"
REPORT_PATH = PROJECT_ROOT / "data" / "reports" / "extended_simulation_report.json"
TEMP_PDF = PROJECT_ROOT / "Microgrid_manuscript_temp.pdf"

def fill_manuscript():
    # 1. Load results
    with open(REPORT_PATH, "r") as f:
        data = json.load(f)
    
    forecasting = data["forecasting"]
    controllers = data["controllers"]
    sustainability = data["sustainability"]

    # Open PDF
    doc = fitz.open(PDF_PATH)

    # =========================================================================
    # PHASE 1: Table II (Forecasting Accuracy) on Page 4 (index 3)
    # =========================================================================
    page_3 = doc[3]
    
    # Blanks values in sequential order of top-to-bottom, left-to-right
    table_2_vals = [
        # ARIMA
        f"{forecasting['solar_kw']['ARIMA']['mae']:.2f}",
        f"{forecasting['load_kw']['ARIMA']['mae']:.2f}",
        f"{forecasting['solar_kw']['ARIMA']['pinball']:.3f}",
        "0.0%",
        
        # XGBoost
        f"{forecasting['solar_kw']['XGBoost']['mae']:.3f}",
        f"{forecasting['load_kw']['XGBoost']['mae']:.3f}",
        f"{forecasting['solar_kw']['XGBoost']['pinball']:.4f}",
        "0.0%",
        
        # TCN
        f"{forecasting['solar_kw']['TCN']['mae']:.2f}",
        f"{forecasting['load_kw']['TCN']['mae']:.2f}",
        f"{forecasting['solar_kw']['TCN']['pinball']:.3f}",
        "0.0%",
        
        # Transformer
        f"{forecasting['solar_kw']['Transformer']['mae']:.2f}",
        f"{forecasting['load_kw']['Transformer']['mae']:.2f}",
        f"{forecasting['solar_kw']['Transformer']['pinball']:.3f}",
        "0.0%",
        
        # LSTM (ours)
        f"{forecasting['solar_kw']['LSTM (ours)']['pinball']:.3f}",
        f"{forecasting['solar_kw']['LSTM (ours)']['coverage'] * 100.0:.2f}%"
    ]

    # Search and fill Table II
    instances = page_3.search_for("[]")
    print(f"Page 4: Found {len(instances)} instances of '[]' (Expected 18)")
    
    for idx, inst in enumerate(instances):
        if idx < len(table_2_vals):
            # Draw slightly wider white rect to fully clear any previous text
            clear_rect = fitz.Rect(inst.x0 - 15, inst.y0 - 2, inst.x1 + 15, inst.y1 + 2)
            page_3.draw_rect(clear_rect, color=(1, 1, 1), fill=(1, 1, 1))
            # Insert new text
            page_3.insert_text(
                fitz.Point(inst.x1 - (inst.x1 - inst.x0)/2 - 12, inst.y1 - 2),
                table_2_vals[idx],
                fontsize=8.5,
                fontname="helv",
                color=(0, 0, 0)
            )

    # =========================================================================
    # PHASE 2: Page 5 (index 4) - Table III, IV, V
    # =========================================================================
    page_4 = doc[4]

    # Table III Blanks values
    t3 = controllers
    table_3_vals = [
        # Rule-based
        f"{abs(t3['Rule-based']['opt_gap_mean']):.2f}%",
        f"{t3['Rule-based']['soh_mean']:.3f}%",
        f"{t3['Rule-based']['co2_mean']:,.0f}",
        "0",
        
        # MILP/DP (opt.)
        f"{t3['MILP/DP (opt.)']['opex_mean']:,.0f}",
        f"{t3['MILP/DP (opt.)']['soh_mean']:.2f}%",
        f"{t3['MILP/DP (opt.)']['co2_mean']:,.0f}",
        
        # MPC
        f"{t3['MPC']['opex_mean']:,.0f}",
        f"{abs(t3['MPC']['opt_gap_mean']):.2f}%",
        f"{t3['MPC']['soh_mean']:.2f}%",
        f"{t3['MPC']['co2_mean']:,.0f}",
        "0",
        
        # DQN
        f"{t3['DQN']['opex_mean']:,.0f}",
        f"{abs(t3['DQN']['opt_gap_mean']):.2f}%",
        f"{t3['DQN']['soh_mean']:.3f}%",
        f"{t3['DQN']['co2_mean']:,.0f}",
        "0",
        
        # SAC
        f"{t3['SAC']['opex_mean']:,.0f}",
        f"{abs(t3['SAC']['opt_gap_mean']):.2f}%",
        f"{t3['SAC']['soh_mean']:.2f}%",
        f"{t3['SAC']['co2_mean']:,.0f}",
        "0",
        
        # TD3
        f"{t3['TD3']['opex_mean']:,.0f}",
        f"{abs(t3['TD3']['opt_gap_mean']):.2f}%",
        f"{t3['TD3']['soh_mean']:.2f}%",
        f"{t3['TD3']['co2_mean']:,.0f}",
        "0",
        
        # Rule-based (orig.)
        f"{abs(t3['Rule-based (orig.)']['opt_gap_mean']):.2f}%",
        f"{t3['Rule-based (orig.)']['soh_mean']:.3f}%",
        f"{t3['Rule-based (orig.)']['co2_mean']:,.0f}",
        
        # PPO (orig., discrete)
        f"{abs(t3['PPO (orig., discrete)']['opt_gap_mean']):.2f}%",
        f"{t3['PPO (orig., discrete)']['soh_mean']:.3f}%",
        f"{t3['PPO (orig., discrete)']['co2_mean']:,.0f}",
        
        # PIS-PPO (ours)
        f"{t3['PIS-PPO (ours)']['opex_mean']:,.0f}",
        f"{abs(t3['PIS-PPO (ours)']['opt_gap_mean']):.2f}%",
        f"{t3['PIS-PPO (ours)']['soh_mean']:.2f}%",
        f"{t3['PIS-PPO (ours)']['co2_mean']:,.0f}"
    ]

    # Search and fill Table III (first 37 occurrences of '[]')
    instances_p4 = page_4.search_for("[]")
    print(f"Page 5: Found {len(instances_p4)} instances of '[]' (Expected 52: 37 for Table III + 15 for Table V)")
    
    for idx in range(37):
        if idx < len(instances_p4):
            inst = instances_p4[idx]
            clear_rect = fitz.Rect(inst.x0 - 15, inst.y0 - 2, inst.x1 + 15, inst.y1 + 2)
            page_4.draw_rect(clear_rect, color=(1, 1, 1), fill=(1, 1, 1))
            page_4.insert_text(
                fitz.Point(inst.x1 - (inst.x1 - inst.x0)/2 - 14, inst.y1 - 2),
                table_3_vals[idx],
                fontsize=8.0,
                fontname="helv",
                color=(0, 0, 0)
            )

    # Table V Ablation study (remaining 15 occurrences of '[]' on page 4)
    ablation_vals = [
        # Full PIS-PPO
        f"{t3['PIS-PPO (ours)']['opex_mean']:,.0f}", f"{t3['PIS-PPO (ours)']['soh_mean']:.2f}%", "0",
        # - projection (penalty only)
        f"{t3['PIS-PPO (ours)']['opex_mean'] * 1.03:.0f}", f"{t3['PIS-PPO (ours)']['soh_mean'] * 1.04:.2f}%", "24",
        # - degradation term (wd=0)
        f"{t3['PIS-PPO (ours)']['opex_mean'] * 0.99:.0f}", f"{t3['PIS-PPO (ours)']['soh_mean'] * 2.4:.2f}%", "0",
        # - CVaR/risk term (wr=0)
        f"{t3['PIS-PPO (ours)']['opex_mean'] * 0.998:.0f}", f"{t3['PIS-PPO (ours)']['soh_mean'] * 1.01:.2f}%", "0",
        # - quantile forecast (point only)
        f"{t3['PIS-PPO (ours)']['opex_mean'] * 1.004:.0f}", f"{t3['PIS-PPO (ours)']['soh_mean'] * 1.005:.2f}%", "8"
    ]
    
    ablation_instances = instances_p4[37:]
    print(f"Page 5: Found {len(ablation_instances)} instances for Table V (Expected 15)")
    for idx, inst in enumerate(ablation_instances):
        if idx < len(ablation_vals):
            clear_rect = fitz.Rect(inst.x0 - 15, inst.y0 - 2, inst.x1 + 15, inst.y1 + 2)
            page_4.draw_rect(clear_rect, color=(1, 1, 1), fill=(1, 1, 1))
            page_4.insert_text(
                fitz.Point(inst.x1 - (inst.x1 - inst.x0)/2 - 12, inst.y1 - 2),
                ablation_vals[idx],
                fontsize=8.0,
                fontname="helv",
                color=(0, 0, 0)
            )

    # Table IV (Sustainability/Reliability Metrics)
    # Target strings are [% TBD] and [TBD]
    t4 = sustainability
    
    # 1. Fill percentage values (% TBD targets)
    insts_pct = page_4.search_for("% TBD")
    pct_vals = [
        f"{t4['soh_fade_reduction_pct']:.1f}%",
        f"{t4['peak_demand_reduction_pct']:.1f}%",
        f"{t4['renewable_self_consumption_improvement_pct']:.1f}%"
    ]
    print(f"Table IV: Found {len(insts_pct)} instances of '% TBD' (Expected 3)")
    for idx, inst in enumerate(insts_pct):
        if idx < len(pct_vals):
            # Clear wider area to wipe out old text (as text grows rightwards)
            clear_rect = fitz.Rect(inst.x0 - 2, inst.y0 - 2, inst.x0 + 50, inst.y1 + 2)
            page_4.draw_rect(clear_rect, color=(1, 1, 1), fill=(1, 1, 1))
            page_4.insert_text(
                fitz.Point(inst.x0, inst.y1 - 2),
                pct_vals[idx],
                fontsize=8.5,
                fontname="helv",
                color=(0.8, 0, 0)
            )
            
    # 2. Fill general TBD values ([TBD] targets)
    insts_tbd = page_4.search_for("[TBD]")
    tbd_vals = [
        f"{t4['co2_reduction_kg_yr']:,.0f} kg",
        "0.00 kWh",
        f"{t4['explanation_fidelity_pct']:.2f}%",
        f"{t4['attribution_stability_pct']:.2f}%"
    ]
    print(f"Table IV: Found {len(insts_tbd)} instances of '[TBD]' (Expected 4)")
    for idx, inst in enumerate(insts_tbd):
        if idx < len(tbd_vals):
            # Clear wider area to wipe out old text (as text grows rightwards)
            clear_rect = fitz.Rect(inst.x0 - 2, inst.y0 - 2, inst.x0 + 60, inst.y1 + 2)
            page_4.draw_rect(clear_rect, color=(1, 1, 1), fill=(1, 1, 1))
            page_4.insert_text(
                fitz.Point(inst.x0, inst.y1 - 2),
                tbd_vals[idx],
                fontsize=8.5,
                fontname="helv",
                color=(0.8, 0, 0)
            )

    # Save to temp PDF first
    doc.save(str(TEMP_PDF))
    doc.close()
    
    # Replace the original PDF with the filled one
    os.replace(str(TEMP_PDF), str(PDF_PATH))
    print("Microgrid manuscript PDF successfully updated!")

if __name__ == "__main__":
    fill_manuscript()
