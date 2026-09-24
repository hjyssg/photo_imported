#!/bin/bash
# ============================================================
#  DJI Pocket 3 视频批量压缩脚本 (Bash / Git-Bash / MSYS2)
#  将视频压缩为 1080p@30fps | H.265 ~6Mbps | AAC 128k
#
#  用法:  ./compress-dji-videos.sh <文件夹路径>
#  例:    ./compress-dji-videos.sh "/e/_Photo/2026/0830/舞台"
# ============================================================

INPUT_DIR="$1"
OUTPUT_DIR="$INPUT_DIR/compressed"

# --- 参数检查 ---
if [ -z "$INPUT_DIR" ]; then
    echo "用法: $0 <文件夹路径>"
    echo "例:   $0 \"/e/_Photo/2026/0830/舞台\""
    exit 1
fi

# 统一路径格式：MSYS /e/ 转 Windows E:/ (FFmpeg 在 Windows 需要原生路径)
INPUT_DIR=$(cygpath -w "$INPUT_DIR" 2>/dev/null | tr '\\' '/' || echo "$INPUT_DIR")
# 如果用户输入了 C:\ 格式，转成 C:/
INPUT_DIR=$(echo "$INPUT_DIR" | sed 's|\\|/|g')

if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ 错误: 文件夹不存在 → $INPUT_DIR"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# --- 统计 MP4 文件 (case-insensitive glob) ---
shopt -s nocaseglob nullglob
files=("$INPUT_DIR"/*.mp4)
shopt -u nocaseglob nullglob

total=${#files[@]}

if [ "$total" -eq 0 ]; then
    echo "⚠ 在 '$INPUT_DIR' 中没有找到 MP4 文件"
    exit 0
fi

# 检查 bc 是否可用
BC_OK=false
command -v bc &>/dev/null && BC_OK=true

# --- 打印摘要 ---
echo ""
echo "═══════════════════════════════════════════════════"
echo "  DJI Pocket 3  视频归档压缩"
echo "  1080p@30fps | H.265 ~6Mbps | AAC 128k"
echo "═══════════════════════════════════════════════════"
echo "  输入: $INPUT_DIR"
echo "  输出: $OUTPUT_DIR"
echo "  文件: $total 个 MP4"
echo "═══════════════════════════════════════════════════"
echo ""

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

    echo "━━━ [$count/$total] ━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📄 $basename"

    # --- 跳过已存在的输出 ---
    if [ -f "$output" ]; then
        orig_size=$(stat -c%s "$file" 2>/dev/null)
        comp_size=$(stat -c%s "$output" 2>/dev/null)
        echo "  ⏭  已存在，跳过"
        [ -n "$orig_size" ] && [ -n "$comp_size" ] && [ "$comp_size" -gt 0 ] && \
            if $BC_OK; then
                echo "      压缩比: $(echo "scale=1; 100 * $comp_size / $orig_size" | bc)%"
            else
                echo "      压缩比: $(( 100 * comp_size / orig_size ))%"
            fi
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
        echo "  ⏱  原始时长: ${minutes}m${seconds}s"
    else
        echo "  ⏱  时长: 未知 (继续处理)"
    fi

    # --- FFmpeg 编码 (直接写入输出文件，失败时清理) ---
    t1=$(date +%s)

    ffmpeg -y -hwaccel auto \
        -i "$file" \
        -c:v libx265 \
        -b:v 6M \
        -maxrate 8M \
        -bufsize 12M \
        -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
        -r 30 \
        -pix_fmt yuv420p \
        -c:a aac \
        -b:a 128k \
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
            orig_size=$(stat -c%s "$file" 2>/dev/null || echo 0)

            if [ "$comp_size" -gt 0 ] 2>/dev/null; then
                comp_mb=$(echo "scale=1; $comp_size / 1048576" | bc 2>/dev/null || echo "$(( comp_size / 1048576 ))")
                echo "  ✅ 完成  |  耗时: ${elapsed}s  |  速度: ${speed}x"
                echo "     大小: ${comp_mb}MB"

                if [ "$orig_size" -gt 0 ] 2>/dev/null; then
                    if $BC_OK; then
                        ratio=$(echo "scale=1; 100 * $comp_size / $orig_size" | bc)
                    else
                        ratio=$(( 100 * comp_size / orig_size ))
                    fi
                    echo "     压缩比: ${ratio}%"
                fi
            else
                echo "  ✅ 完成  |  耗时: ${elapsed}s"
            fi
        fi

        processed=$((processed + 1))

        # --- ETA 估算 ---
        done_so_far=$((processed + failed))
        if [ "$done_so_far" -gt 0 ] && [ "$done_so_far" -lt "$total" ]; then
            now=$(date +%s)
            run_time=$((now - start_ts))
            avg_time=$((run_time / done_so_far))
            [ "$avg_time" -lt 1 ] && avg_time=1
            remaining_files=$((total - done_so_far))
            eta=$((remaining_files * avg_time))

            eta_min=$((eta / 60))
            eta_sec=$((eta % 60))
            echo "  📊 预估剩余: ${eta_min}m${eta_sec}s  (平均 ${avg_time}s/个)"
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

echo "═══════════════════════════════════════════════════"
echo "  全部完成！总耗时: ${time_min}m${time_sec}s"
echo ""
echo "  ✅ 成功压缩: $processed"
echo "  ⏭  已跳过(文件已存在): $skipped"
echo "  ❌ 失败: $failed"
echo ""
echo "  输出目录: $OUTPUT_DIR"
echo "═══════════════════════════════════════════════════"
echo ""