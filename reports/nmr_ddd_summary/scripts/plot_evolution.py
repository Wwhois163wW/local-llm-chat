#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# reports/nmr_ddd_summary/scripts/plot_evolution.py
# Author: ZHU, W. phD @gemini

import json
import matplotlib.pyplot as plt
import os

def Plot_Comparison():
    data_path = os.path.join("reports", "nmr_ddd_summary", "data", "performance_deep.json")
    if not os.path.exists(data_path):
        print("Data not found!")
        return
        
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    keys = list(data.keys())
    labels = ["V1", "V2", "V3 (Std)", "V3 (Opt)"]
    
    # 1. Accuracy Plot (Triple Layer)
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    x = range(len(keys))
    width = 0.25
    
    key_acc = [data[k]["accuracy"]["Key"] for k in keys]
    target_acc = [data[k]["accuracy"]["Target"] for k in keys]
    global_acc = [data[k]["accuracy"]["Global"] for k in keys]
    
    ax1.bar([i - width for i in x], key_acc, width, label='Key Fields', color='#CC0000', edgecolor='black')
    ax1.bar(x, target_acc, width, label='Target Fields', color='#333333', edgecolor='black')
    ax1.bar([i + width for i in x], global_acc, width, label='Global Accuracy', color='#999999', edgecolor='black')
    
    ax1.set_ylabel('Accuracy (%)')
    ax1.set_title('Evolution & Infrastructure Impact: Accuracy Benchmarks')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylim(0, 120)
    ax1.legend(loc='upper left')
    ax1.grid(axis='y', linestyle='--', alpha=0.3)
    
    for i in x:
        ax1.text(i - width, key_acc[i] + 2, f'{key_acc[i]}%', ha='center', fontsize=8, rotation=45)
        ax1.text(i, target_acc[i] + 2, f'{target_acc[i]}%', ha='center', fontsize=8, rotation=45)
        ax1.text(i + width, global_acc[i] + 2, f'{global_acc[i]}%', ha='center', fontsize=8, rotation=45)

    plt.tight_layout()
    out1 = os.path.join("reports", "nmr_ddd_summary", "assets", "accuracy_evolution.png")
    plt.savefig(out1, dpi=300)
    
    # 2. Efficiency & Load Plot (Latency vs Token Count)
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    latencies = [data[k]["efficiency"]["Latency"] for k in keys]
    tokens = [data[k]["efficiency"]["Total_Tokens"] for k in keys]
    
    # 用柱状图展示 Token 负载 (反映语义重量)
    ax2.bar(labels, tokens, color='#EEEEEE', edgecolor='#333333', label='Avg Token Load', alpha=0.8)
    ax2.set_ylabel('Avg Token Count', color='#333333')
    ax2.set_ylim(0, max(tokens) * 1.2)
    
    # 用折线图展示 Latency (反映响应性能)
    ax2_r = ax2.twinx()
    ax2_r.plot(labels, latencies, marker='o', color='#CC0000', linewidth=2, label='Latency (s/rec)')
    ax2_r.set_ylabel('Latency (seconds)', color='#CC0000')
    ax2_r.tick_params(axis='y', labelcolor='#CC0000')
    ax2_r.set_ylim(0, max(latencies) * 1.2)
    
    plt.title('Infrastructure Impact: Latency vs Token Load')
    fig2.tight_layout()
    ax2.legend(loc='upper left')
    ax2_r.legend(loc='upper right')
    
    out2 = os.path.join("reports", "nmr_ddd_summary", "assets", "efficiency_compare.png")
    plt.savefig(out2, dpi=300)
    
    print(f"Refined Efficiency Plots saved to assets/")

if __name__ == "__main__":
    Plot_Comparison()
