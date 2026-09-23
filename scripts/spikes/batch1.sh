#!/bin/zsh
# S7 edits, S5 turbo, S6 prompt enhancers, uncensored variant — one job at a time.
cd "$(dirname "$0")"
export PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1 SDNQ_USE_TORCH_COMPILE=0 TOKENIZERS_PARALLELISM=false \
       QWEN_STUDIO_ATTN_BUDGET_MB=512 QWEN_STUDIO_KV_BUDGET_GB=6 QWEN_STUDIO_DTYPE=auto
py=../../.venv/bin/python
run() { echo "===== $1 $(date +%T)"; $py -u run_job.py "$@" 2>&1 | grep -E "^\[|\"error\"|Saved|Traceback|Error" ; }
S=space
run s7_edit_hair --ratio-mode reference --preset custom --steps 12 --image $S/2d02ee93-6278-4aa9-8fb9-3ca8d4c89dbb.webp \
  --prompt 'Change the young woman'"'"'s hairstyle from the tied-up bun to long voluminous big wavy curls falling naturally over her shoulders. This is a local edit: keep the framing, composition, her face and everything else unchanged.'
run s7_edit_mask --ratio-mode reference --preset custom --steps 12 --image $S/d085337f-fdc8-419c-8f6f-fd21f32a612e.webp --image $S/a5fa8e4a-9064-402e-b7d2-3d6254af97cb.webp \
  --prompt '图中画圈标注的地方需要补上一名骑坐姿态的西部牛仔男子。他头戴棕色宽檐牛仔帽，蓄着浓密的络腮胡，脸侧向画面左方；上身穿棕色帆布夹克，里面搭配深蓝色牛仔衬衫，颈间系着浅棕色围巾；下身穿着带流苏的棕色皮质护腿，脚穿皮靴踩进马镫，一只手搭在鞍部附近，整体呈现自然的骑乘状态。'
run s7_edit_marks --ratio-mode reference --preset custom --steps 12 --image $S/7922c916-518b-4c07-a7d1-819ecc4ae88c.webp \
  --prompt '将蓝色框选区域内佩戴在抬起手腕上的棕色皮表带金属手表整体移除，并以与手臂肤色及明暗过渡一致的皮肤自然延续填补腕部区域；将红色框选区域内男生的蓬松金色头发改为黑色；将两处绿色框选区域内的衣服换成灰色短袖亚麻睡衣；蓝色、红色与绿色标注线不得渲染在图像中。'
run s7_edit_5refs --ratio-mode reference --preset custom --steps 12 --image $S/447da49d-dcd0-46ec-9ca8-20127c0f07d1.webp --image $S/0f2d052b-6ccf-46e2-821d-d073ead679ac.webp --image $S/3f4d7519-6c33-491f-bad8-661f1bf03601.webp --image $S/0f5d38f9-d04a-498e-aaef-9dae01da8c6d.webp --image $S/3acf3276-0572-490e-b8ce-334833a6ca20.webp \
  --prompt '让【图1】中的模特换上【图3】中的玛丽珍鞋，拿着【图4】中的手提包，并戴上【图5】中的绒毛帽。将【图2】中的羽绒服敞开穿在外面，露出原有的内搭上衣。保持模特姿势和背景不变。'
run s5_turbo_t2i --preset turbo --size 1024x1024 \
  --prompt 'A minimalist poster of a paper origami crane on a pale blue background, the title "TURBO" in bold letters at the top.'
run s5_turbo_rgba --preset turbo --size 1024x1024 --transparent \
  --prompt 'A cute cartoon robot mascot waving, full body, clean outlines.'
run s6_pe_t2i --preset turbo --size 1024x1024 --enhance --ratio-mode auto \
  --prompt 'a lighthouse at dawn'
run s6_pe_i2i --preset turbo --ratio-mode auto --enhance --size 1024x1024 --image $S/8c265cf7-51ec-44fd-9436-30fbd96491de.webp \
  --prompt 'restore and colorize this old photo'
run s8_uc_t2i --variant uc --preset custom --steps 12 --size 1024x1024 \
  --prompt 'A cozy bookstore window display on a rainy evening, warm light, a hand-painted wooden sign above the door reads "Qwen Image 2.1 Studio", a sleeping ginger cat on a stack of books, photorealistic, 35mm'
echo "===== done $(date +%T)"
