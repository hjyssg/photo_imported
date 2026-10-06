#!/bin/bash
# ============================================================
#  DJI/相机视频批量压缩脚本 (Bash / Git-Bash / MSYS2)
#  将视频压缩为 1080p@30fps | H.265 ~6Mbps | AAC 128k
#
#  用法:
#    ./compress-dji-videos.sh -dir "E:/_Photo/2026/0830/舞台"
#    ./compress-dji-videos.sh -dir "E:/_Photo/2026/0830/舞台" --dry
#
#  可配置参数 (修改脚本顶部变量):
#    RESOLUTION  输出分辨率 (默认 1920x1080)
#    VIDEO_BITRATE  视频码率 (默认 6M)
#    FPS  帧率 (默认 30)
# ============================================================

# ============ 可配置参数 ============
RESOLUTION="1920:1080"
VIDEO_BITRATE="6M"
MAXRATE="8M"
BUF_SIZE="12M"
FPS="30"
AUDIO_BITRATE="128k"
# ===================================

INPUT_DIR=""
DRY_RUN=false

# --- 参数解析 ---
while [ $# -gt 0 ]; do
    case "$1" in
        -dir|--dir|--directory|-d)
            INPUT_DIR="$2"
            shift 2
            ;;
        --dry|--preview|-n)
            DRY_RUN=true
            shift
            ;;
        -h|--help|--usage)
            echo ""
            echo "  视频批量压缩工具"
            echo "  用法: $0 -dir <文件夹路径> [选项]"
            echo ""
            echo "  选项:"
            echo "    -dir <路径>     要压缩的视频文件夹 (必填)"
            echo "    --dry           预览模式，不实际压缩"
            echo "    -h, --help      显示帮助"
            echo ""
            echo "  示例:"
            echo "    $0 -dir \"E:/_Photo/2026/0830/舞台\""
            echo "    $0 -dir \"/e/_Photo/2026/0830/舞台\" --dry"
            echo ""
            exit 0
            ;;
        *)
            # 向后兼容：如果没有 -dir 前缀，当作位置参数
            if [ -z "$INPUT_DIR" ]; then
                INPUT_DIR="$1"
            fi
            shift
            ;;
    esac
done

OUTPUT_DIR="$INPUT_DIR/compressed"

# --- 参数检查 ---
if [ -z "$INPUT_DIR" ]; then
    echo ""
    echo "  ❌ 错误: 请指定文件夹路径"
    echo "  用法: $0 -dir <文件夹路径>"
    echo "  例:   $0 -dir \"E:/_Photo/2026/0830/舞台\""
    echo ""
    exit 1
fi

# 统一路径格式：MSYS /e/ 转 Windows E:/ (FFmpeg 在 Windows 需要原生路径)
INPUT_DIR=$(cygpath -w "$INPUT_DIR" 2>/dev/null | tr '\\\\' '/' || echo "$INPUT_DIR")
# 如果用户输入了 C:\\ 格式，转成 C:/
INPUT_DIR=$(echo "$INPUT_DIR" | sed 's|\\\\|/|g')

if [ ! -d "$INPUT_DIR" ]; then
    echo "  ❌ 错误: 文件夹不存在 → $INPUT_DIR"
    exit 1
fi

# --- 统计 MP4 文件 (case-insensitive glob) ---
shopt -s nocaseglob nullglob
files=("$INPUT_DIR"/*.mp4)
shopt -u nocaseglob nullglob

total=${#files[@]}

if [ "$total" -eq 0 ]; then
    echo "  ⚠ 在 '$INPUT_DIR' 中没有找到 MP4 文件"
    exit 0
fi

# 检查 bc 是否可用
BC_OK=false
command -v bc &>/dev/null && BC_OK=true

# --- 打印摘要 ---
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       🎬  视频批量压缩                                    ║"
echo "║       ${RESOLUTION} @ ${FPS}fps | H.265 ~${VIDEO_BITRATE} | AAC ${AUDIO_BITRATE}            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  📂 输入: $INPUT_DIR"
echo "  📂 输出: $OUTPUT_DIR"
echo "  📊 文件: $total 个 MP4"
if $DRY_RUN; then
    echo "  👁  模式: 预览 (--dry) — 不会编码"
fi
echo ""

if $DRY_RUN; then
    echo "  --- 预览: 待处理的文件 ---"
    i=0
    for file in "${files[@]}"; do
        i=$((i+1))
        basename=$(basename "$file")
        size=$(stat -c%s "$file" 2>/dev/null || echo 0)
        size_mb=$(echo "scale=1; $size / 1048576" | bc 2>/dev/null || echo "$((size/1048576))")
        duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$file" 2>/dev/null)
        dur_sec=${duration%.*}
        if [ -n "$dur_sec" ] && [ "$dur_sec" -gt 0 ] 2>/dev/null; then
            minutes=$((dur_sec / 60))
            seconds=$((dur_sec % 60))
            echo "  [$i/$total]  $basename  (${minutes}m${seconds}s, ${size_mb}MB)"
        else
            echo "  [$i/$total]  $basename  (${size_mb}MB)"
        fi
    done
    echo ""
    echo "  ✅ 预览完成。去掉 --dry 即可执行压缩。"
    echo ""
    exit 0
fi

# --- 确保输出目录存在 (FFmpeg 不会自动创建目录) ---
mkdir -p "$OUTPUT_DIR"

# --- 主循环 ---
count=0
processed=0
skipped=0
failed=0
start_ts=$(date +%s)

for file in "${files[@]}"; do
    basename=$(basename "$file")
    output="$OUTPUT_DIR/$basename"
    count=$((count + 1))

    echo "━━━ [$count/$total] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📄 $basename"

    # --- 进度条初始化 ---
    orig_size=$(stat -c%s "$file" 2>/dev/null || echo 0)
    orig_mb=$(echo "scale=1; $orig_size / 1048576" | bc 2>/dev/null || echo "$(( orig_size / 1048576 ))")

    # --- 跳过已存在的输出 ---
    if [ -f "$output" ]; then
        comp_size=$(stat -c%s "$output" 2>/dev/null)
        echo "  ⏭  已存在，跳过"
        [ -n "$orig_size" ] && [ -n "$comp_size" ] && [ "$comp_size" -gt 0 ] && \
            if $BC_OK; then
                ratio=$(echo "scale=1; 100 * $comp_size / $orig_size" | bc)
            else
                ratio=$(( 100 * comp_size / orig_size ))
            fi
            echo "     大小: $(echo "scale=1; $comp_size / 1048576" | bc 2>/dev/null)MB  |  压缩比: ${ratio}%"
        skipped=$((skipped + 1))
        echo ""
        continue
    fi

    # --- 获取原始视频时长 (秒) ---
    duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$file" 2>/dev/null)
    dur_sec=${duration%.*}
    [ -z "$dur_sec" ] || [ "$dur_sec" -eq 0 ] 2>/dev/null && dur_sec=0

    if [ "$dur_sec" -gt 0 ]; then
        minutes=$((dur_sec / 60))
        seconds=$((dur_sec % 60))
        echo "  ⏱  时长: ${minutes}m${seconds}s  |  原始: ${orig_mb}MB"
    else
        echo "  ⏱  原始: ${orig_mb}MB"
    fi

    # --- FFmpeg 编码 ---
    t1=$(date +%s)

    ffmpeg -y -hwaccel auto \
        -i "$file" \
        -c:v libx265 \
        -b:v "$VIDEO_BITRATE" \
        -maxrate "$MAXRATE" \
        -bufsize "$BUF_SIZE" \
        -vf "scale=${RESOLUTION}:force_original_aspect_ratio=decrease,pad=${RESOLUTION}:(ow-iw)/2:(oh-ih)/2:black" \
        -r "$FPS" \
        -pix_fmt yuv420p \
        -c:a aac \
        -b:a "$AUDIO_BITRATE" \
        -map_metadata 0 \
        -movflags write_colr \
        -tag:v hvc1 \
        -x265-params "no-open-gop=1:log-level=error" \
        -stats \
        "$output" 2>&1

    exit_code=$?

    if [ $exit_code -eq 0 ] && [ -f "$output" ]; then
        t2=$(date +%s)
        elapsed=$((t2 - t1))

        # 计算编码速度 (x 倍速)
        if [ "$dur_sec" -gt 0 ] && [ "$elapsed" -gt 0 ]; then
            if $BC_OK; then
                speed=$(echo "scale=2; $dur_sec / $elapsed" | bc 2>/dev/null || echo "?")
            else
                speed=$(( dur_sec / elapsed ))
            fi
        else
            speed="?"
        fi

        # 输出文件大小
        if [ -f "$output" ]; then
            comp_size=$(stat -c%s "$output" 2>/dev/null || echo 0)

            if [ "$comp_size" -gt 0 ] 2>/dev/null; then
                comp_mb=$(echo "scale=1; $comp_size / 1048576" | bc 2>/dev/null || echo "$(( comp_size / 1048576 ))")

                # 原始/压缩比例
                if $BC_OK; then
                    ratio=$(echo "scale=1; 100 * $comp_size / $orig_size" | bc)
                else
                    ratio=$(( 100 * comp_size / orig_size ))
                fi

                # 节省百分比
                saved=$((100 - ${ratio%.*}))
                [ "$saved" -lt 0 ] && saved=0

                echo "  ✅ 完成  |  ${elapsed}s  |  ${speed}x  |  ${comp_mb}MB  |  压缩比 ${ratio}%  |  节省 ${saved}% 🎯"
            else
                echo "  ✅ 完成  |  耗时: ${elapsed}s"
            fi
        fi

        processed=$((processed + 1))

        # --- ETA 估算和进度条 ---
        done_so_far=$((processed + skipped + failed))
        if [ "$done_so_far" -gt 0 ] && [ "$done_so_far" -lt "$total" ]; then
            now=$(date +%s)
            run_time=$((now - start_ts))
            avg_time=$((run_time / done_so_far))
            [ "$avg_time" -lt 1 ] && avg_time=1
            remaining_files=$((total - done_so_far))
            eta=$((remaining_files * avg_time))

            eta_min=$((eta / 60))
            eta_sec=$((eta % 60))

            # 进度条 (简易 ASCII)
            bar_width=30
            progress=$((done_so_far * bar_width / total))
            bar=""
            for ((p=0; p<progress; p++)); do bar="${bar}█"; done
            for ((p=progress; p<bar_width; p++)); do bar="${bar}░"; done
            pct=$((done_so_far * 100 / total))

            echo "  📊 [$bar] ${pct}%  |  已处理 ${done_so_far}/${total}  |  剩余约 ${eta_min}m${eta_sec}s"
        fi
    else
        echo "  ❌ 失败 (exit code: $exit_code)"
        [ -f "$output" ] && rm -f "$output"
        failed=$((failed + 1))
    fi
    echo ""

done

# --- 完成报告 ---
end_ts=$(date +%s)
total_time=$((end_ts - start_ts))
time_min=$((total_time / 60))
time_sec=$((total_time % 60))

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  🎉  全部完成！                                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  ⏱  总耗时: ${time_min}m${time_sec}s"
echo "  ✅ 成功压缩: $processed"
echo "  ⏭  跳过: $skipped"
echo "  ❌ 失败: $failed"
echo ""
echo "  📂 输出: $OUTPUT_DIR"
echo ""

# 汇总节省空间
if [ "$processed" -gt 0 ]; then
    total_orig=0
    total_comp=0
    for file in "${files[@]}"; do
        s=$(stat -c%s "$file" 2>/dev/null || echo 0)
        total_orig=$((total_orig + s))
        base=$(basename "$file")
        comp_file="$OUTPUT_DIR/$base"
        if [ -f "$comp_file" ]; then
            s2=$(stat -c%s "$comp_file" 2>/dev/null || echo 0)
            total_comp=$((total_comp + s2))
        fi
    done
    if [ "$total_comp" -gt 0 ] && [ "$total_orig" -gt 0 ]; then
        if $BC_OK; then
            total_ratio=$(echo "scale=1; 100 * $total_comp / $total_orig" | bc)
        else
            total_ratio=$(( 100 * total_comp / total_orig ))
        fi
        total_orig_mb=$(echo "scale=1; $total_orig / 1048576" | bc 2>/dev/null)
        total_comp_mb=$(echo "scale=1; $total_comp / 1048576" | bc 2>/dev/null)
        saved_pct=$((100 - ${total_ratio%.*}))
        echo "  💾 空间统计:  ${total_orig_mb}MB → ${total_comp_mb}MB  (节省 ${saved_pct}%)"
        echo ""
    fi
fi