#!/usr/bin/env bash
# Sequential, resumable downloads of the Hugging Face models used by the workflows.
# Usage: COMFY_MODELS=/path/to/ComfyUI/models bash scripts/download_models.sh [all|krea|h3|moss|extras]
# Community LoRAs/finetunes from Civitai are NOT downloaded here (login required) — see README.
set -u
M="${COMFY_MODELS:?Set COMFY_MODELS to your ComfyUI models folder}"
HF="https://huggingface.co"
WHAT="${1:-all}"
get() { # folder url
  local dir="$M/$1" url="$2" name; name="$(basename "${url%%\?*}")"
  mkdir -p "$dir"
  if [ -f "$dir/$name" ] && [ ! -f "$dir/$name.part" ]; then echo "SKIP $name"; return; fi
  echo "START $(date +%T) $name"
  if curl -L --fail --retry 5 --retry-delay 10 -C - -sS -o "$dir/$name.part" "$url"; then
    mv -f "$dir/$name.part" "$dir/$name"; echo "DONE  $(date +%T) $name"
  else echo "FAIL  $name"; fi
}
want() { [ "$WHAT" = all ] || [ "$WHAT" = "$1" ]; }
if want krea; then   # stills: 01, 01b
  get diffusion_models "$HF/Comfy-Org/Krea-2/resolve/main/diffusion_models/krea2_turbo_int8_convrot.safetensors"
  get text_encoders    "$HF/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors"
  get vae              "$HF/Comfy-Org/Krea-2/resolve/main/vae/qwen_image_vae.safetensors"
  get vae              "$HF/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"
fi
if want h3; then     # video: 03, 03b, 03c, 05 (05 also needs the Civitai finetune)
  get diffusion_models "$HF/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
  get text_encoders    "$HF/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
  get vae              "$HF/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors"
  get vae              "$HF/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors"
  get loras            "$HF/Comfy-Org/MiniMax-H3/resolve/main/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
  get vae_approx       "$HF/Kijai/MiniMax-H3-TAE/resolve/main/vae_approx/taeh3.safetensors"
fi
if want moss; then   # stills: 02
  get diffusion_models "$HF/Comfy-Org/MOSS-Image/resolve/main/diffusion_models/moss_image_sft_bf16.safetensors"
  get text_encoders    "$HF/Comfy-Org/MOSS-Image/resolve/main/text_encoders/qwen3.5_9b_int8_convrot.safetensors"
  get vae              "$HF/Comfy-Org/MOSS-Image/resolve/main/vae/flux2-vae.safetensors"
fi
if want extras; then # face detailer (01, 02), OmniSR upscale (01, 02, 04 variant); RIFE downloads itself
  get ultralytics/bbox "$HF/Bingsu/adetailer/resolve/main/face_yolov8m.pt"
  get upscale_models   "$HF/Acly/Omni-SR/resolve/main/OmniSR_X4_DIV2K.safetensors"
fi
echo "ALL FINISHED $(date +%T)"
