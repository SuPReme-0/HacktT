#!/bin/bash

# ==========================================
# CONFIGURATION
# ==========================================
CONDA_ENV="hack"

echo "==================================================="
echo "🚀 Launching GPU-Aware 5-Day Ingestion Pipeline..."
echo "==================================================="

# 1. Initialize Conda inside the bash script
# (Adjust the path if you use anaconda3 instead of miniconda3)
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null
conda activate $CONDA_ENV
echo "✅ Activated Conda environment: $CONDA_ENV"

# 2. Function to check GPU health
check_gpu() {
    if ! nvidia-smi > /dev/null 2>&1; then
        return 1 # GPU is unreachable
    fi
    return 0 # GPU is healthy
}

# 3. The Immortal Loop
while true; do
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Probing GPU connection..."
    
    if check_gpu; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] GPU is ONLINE. Initiating Python Orchestrator..."
        
        # Run the master orchestrator
        python src/build/master.py
        EXIT_CODE=$?
        
        # If python exits with exactly 0, the 890k files are finished!
        if [ $EXIT_CODE -eq 0 ]; then
            echo "🏁 [$(date +'%Y-%m-%d %H:%M:%S')] INGESTION COMPLETELY FINISHED!"
            break
        else
            echo "⚠️ [$(date +'%Y-%m-%d %H:%M:%S')] Python crashed with exit code $EXIT_CODE."
        fi
    else
        # If we hit this, the CUDA Drop happened. 
        echo "🚨 CRITICAL: GPU communication lost (TDR Crash or Driver failure)!"
        echo "⏳ Waiting 60 seconds to see if Windows auto-recovers the NVIDIA driver..."
        sleep 50 # Plus the 10 below = 60s
    fi

    echo "🧹 Flushing Linux RAM cache to prevent memory bloat..."
    # This safely forces Linux to dump cached files from RAM
    sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1

    echo "⏳ Respawning in 10 seconds..."
    sleep 10
done