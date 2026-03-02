"""
GPU Verification Script for PylaAI
Run: python tests/test_gpu.py

Checks DirectML availability and benchmarks ONNX inference — no torch needed.
"""
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import onnxruntime as ort


def test_providers():
    providers = ort.get_available_providers()
    print(f"Available providers: {providers}")
    has_dml = "DmlExecutionProvider" in providers
    has_cuda = "CUDAExecutionProvider" in providers
    if has_dml:
        print("✅ DirectML (AMD GPU) available!")
    elif has_cuda:
        print("✅ CUDA (NVIDIA GPU) available!")
    else:
        print("⚠  No GPU provider — CPU only.")
    return has_dml or has_cuda


def test_model_inference(model_path, provider):
    print(f"\nTesting: {model_path}")
    print(f"  Provider: {provider}")

    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

    session = ort.InferenceSession(model_path, sess_options=so, providers=[provider])
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    resolved = []
    for dim in input_shape:
        resolved.append(dim if isinstance(dim, int) else (1 if len(resolved) == 0 else 640))
    dummy = np.random.rand(*resolved).astype(np.float32)

    t0 = time.perf_counter()
    session.run(None, {input_name: dummy})
    cold_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    for _ in range(10):
        session.run(None, {input_name: dummy})
    warm_ms = (time.perf_counter() - t0) / 10 * 1000

    print(f"  Cold: {cold_ms:.1f} ms | Warm: {warm_ms:.1f} ms (avg 10)")
    return True


if __name__ == "__main__":
    print("=" * 55)
    print("  PylaAI — GPU Verification (torch-free)")
    print("=" * 55)

    gpu_ok = test_providers()

    providers = ort.get_available_providers()
    if "DmlExecutionProvider" in providers:
        prov = "DmlExecutionProvider"
    elif "CUDAExecutionProvider" in providers:
        prov = "CUDAExecutionProvider"
    else:
        prov = "CPUExecutionProvider"

    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    ok = True
    for name in ['mainInGameModel.onnx', 'tileDetector.onnx']:
        path = os.path.join(models_dir, name)
        if os.path.exists(path):
            try:
                test_model_inference(path, prov)
            except Exception as e:
                print(f"  ❌ Error: {e}")
                ok = False
        else:
            print(f"\n⚠  Not found: {path}")

    print("\n" + "=" * 55)
    if gpu_ok and ok:
        print("  ✅ All checks passed — GPU ready!")
    elif ok:
        print("  ⚠  Models work, but no GPU provider.")
    else:
        print("  ❌ Some checks failed.")
    print("=" * 55)
