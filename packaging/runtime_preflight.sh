#!/bin/bash
# Sourced by launch.sh; probing never starts the game or modifies its cache.

preflight_error() {
    printf '[preflight] FAIL %s\n' "$*" | tee "$SESSION.preflight.txt"
    return 3
}

runtime_preflight() (
    local tool candidate java_home="${SLAYTHESPIRE_JAVA_HOME:-}" java_image=""
    local weston_home="" weston_image="" scratch="" path
    local java_name="zulu17.54.21-ca-jre17.0.13-linux"
    local weston_name="weston_pkg_0.2"
    local mode="${SLAYTHESPIRE_LAUNCH_MODE:-system-wayland}"
    local -a mounts=()

    preflight_cleanup() {
        local rc=$? mounted
        trap - EXIT
        for mounted in "${mounts[@]}"; do
            if ! ${ESUDO:-} umount "$mounted"; then
                preflight_error "无法释放运行时检查挂载：$mounted"
                rc=3
            fi
        done
        if [ -n "$scratch" ]; then
            rmdir "$scratch/java" "$scratch/weston" "$scratch" 2>/dev/null || true
        fi
        exit "$rc"
    }
    trap preflight_cleanup EXIT
    trap 'exit 143' TERM HUP
    trap 'exit 130' INT

    echo "[preflight] checking runtime dependencies before resource extraction"
    for tool in python3 timeout mount umount mktemp bash unzip zip sha256sum ldd; do
        command -v "$tool" >/dev/null 2>&1 || {
            preflight_error "缺少系统工具：$tool。请检查 RGDSplus 固件与 PortMaster。"
            exit 3
        }
    done
    if [ -z "$CONTROLFOLDER" ] || [ ! -r "$CONTROLFOLDER/control.txt" ]; then
        preflight_error "未找到 PortMaster/control.txt。请先安装或修复 PortMaster。"
        exit 3
    fi
    if [ ! -x "$CONTROLFOLDER/gptokeyb" ]; then
        preflight_error "PortMaster/gptokeyb 缺失或不可执行。请修复 PortMaster。"
        exit 3
    fi
    if ! python3 -c 'import ctypes, fcntl, socket, select, struct' ; then
        preflight_error "Python 3 必要模块不可用。请检查固件的 Python 3 环境。"
        exit 3
    fi
    if [ ! -r /usr/lib/libopenal.so.1 ]; then
        preflight_error "缺少系统音频库 libopenal.so.1。请使用兼容的 RGDSplus 固件。"
        exit 3
    fi
    case "$mode" in
        system-wayland|nested-wayland)
            path="${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}"
            if [ ! -S "$path" ]; then
                preflight_error "显示服务不可用：$path。请从掌机 Ports 菜单启动。"
                exit 3
            fi
            ;;
    esac

    # A bundled runtime is never silently replaced with a shared installation:
    # a damaged/partial card copy must fail before expensive game extraction.
    if [ -d "$APP_DIR/runtime/offline" ]; then
        echo "[preflight] verifying offline Java/Weston images"
        if [ ! -f "$APP_DIR/runtime/offline/SHA256SUMS" ] ||
            [ ! -f "$APP_DIR/runtime/offline/$java_name.squashfs" ] ||
            [ ! -f "$APP_DIR/runtime/offline/$weston_name.squashfs" ] ||
            [ ! -f "$APP_DIR/runtime/offline/libs/libjpeg.so.8" ] ||
            [ ! -f "$APP_DIR/runtime/offline/libs/libXtst.so.6" ] ||
            ! (cd "$APP_DIR/runtime/offline" && sha256sum -c SHA256SUMS); then
            preflight_error "包内离线运行库缺失或校验失败。请重新完整复制适配包的 Ports 文件夹；无需删除正版 JAR、缓存或存档。"
            exit 3
        fi
    fi

    if [ -n "$java_home" ]; then
        if [ ! -x "$java_home/bin/java" ]; then
            preflight_error "指定的 Java 不可执行：$java_home/bin/java"
            exit 3
        fi
    else
        for candidate in "$APP_DIR/runtime/offline/$java_name.squashfs" \
            "$APP_DIR/runtime/java" \
            "$CONTROLFOLDER/libs/$java_name" "$CONTROLFOLDER/libs/$java_name.squashfs"; do
            if [ -x "$candidate/bin/java" ]; then
                java_home="$candidate"
                break
            elif [ -f "$candidate" ]; then
                java_image="$candidate"
                break
            fi
        done
        if [ -z "$java_home" ] && [ -z "$java_image" ]; then
            preflight_error "缺少 Java 17 运行镜像：$java_name.squashfs。请通过 PortMaster 安装到其 libs 目录。"
            exit 3
        fi
    fi

    case "$mode" in
        system-wayland|nested-wayland|upstream-weston)
            for candidate in "$APP_DIR/runtime/offline/$weston_name.squashfs" \
                "$CONTROLFOLDER/libs/$weston_name" \
                "$CONTROLFOLDER/libs/$weston_name.squashfs"; do
                if [ -x "$candidate/westonwrap.sh" ]; then
                    weston_home="$candidate"
                    break
                elif [ -f "$candidate" ]; then
                    weston_image="$candidate"
                    break
                fi
            done
            if [ -z "$weston_home" ] && [ -z "$weston_image" ]; then
                preflight_error "缺少显示运行镜像：$weston_name.squashfs。请通过 PortMaster 安装到其 libs 目录。"
                exit 3
            fi
            ;;
    esac
    scratch=$(mktemp -d /tmp/sts-preflight-XXXXXX) || {
        preflight_error "无法创建运行时检查目录。请检查 /tmp 可用空间。"
        exit 3
    }
    if [ -n "$java_image" ]; then
        mkdir "$scratch/java" || exit 3
        if ! ${ESUDO:-} mount -o ro "$java_image" "$scratch/java"; then
            preflight_error "Java 镜像无法挂载，可能损坏或固件不兼容：$java_image"
            exit 3
        fi
        mounts+=("$scratch/java")
        java_home="$scratch/java"
    fi
    if ! timeout -k 2 15 env -u LD_PRELOAD -u LD_LIBRARY_PATH \
        "$java_home/bin/java" -Xms16m -Xmx32m -version >"$SESSION.java-check.txt" 2>&1; then
        cat "$SESSION.java-check.txt"
        preflight_error "Java 无法运行或检查超时。请修复 Java 17 镜像；详情见本次 java-check.txt 日志。"
        exit 3
    fi
    if ! grep -Eq 'version "17[."]' "$SESSION.java-check.txt"; then
        cat "$SESSION.java-check.txt"
        preflight_error "Java 版本不匹配，需要 Java 17。请检查运行镜像或自定义 Java 路径。"
        exit 3
    fi
    if [ -n "$weston_image" ]; then
        mkdir "$scratch/weston" || exit 3
        if ! ${ESUDO:-} mount -o ro "$weston_image" "$scratch/weston"; then
            preflight_error "Weston 镜像无法挂载，可能损坏或固件不兼容：$weston_image"
            exit 3
        fi
        mounts+=("$scratch/weston")
        weston_home="$scratch/weston"
    fi
    if [ -n "$weston_home" ]; then
        if [ ! -x "$weston_home/westonwrap.sh" ] ||
            ! bash -n "$weston_home/westonwrap.sh"; then
            preflight_error "Weston 镜像中的 westonwrap.sh 缺失、不可执行或损坏。请重新安装显示运行镜像。"
            exit 3
        fi
        # The image's wrapper can be present while its real compositor backend
        # cannot load. Catch missing transitive libraries before extraction.
        for candidate in "$weston_home/wp_weston" \
            "$weston_home/lib_aarch64/libweston-14/headless-backend.so" \
            "$weston_home/lib_aarch64/libweston-14/xwayland.so" \
            "$weston_home/bin/Xwayland"; do
            [ -f "$candidate" ] || continue
            local dependencies
            if ! dependencies=$(timeout -k 2 15 env -u LD_PRELOAD \
                LD_LIBRARY_PATH="$APP_DIR/runtime/offline/libs:$weston_home/lib_aarch64:$weston_home/lib_aarch64/extra_wayland:$weston_home/lib_aarch64/graphics/mesa_x11_stub" \
                ldd "$candidate" 2>&1) ||
                printf '%s\n' "$dependencies" | grep -q 'not found'; then
                printf '%s\n' "$dependencies"
                preflight_error "显示运行库的底层依赖不完整：$(basename "$candidate")。请重新复制完整离线包并检查兼容固件。"
                exit 3
            fi
        done
    fi
    echo "[preflight] PASS runtime checks; resource extraction may proceed"
)

show_preflight_failure() {
    # Keep the explanation independent of the missing Java/Weston runtime.
    # The firmware terminal is optional; the persistent report is always kept.
    NOTICE_SCRIPT=/tmp/sts-rgds-preflight-error-$$.sh
    {
        printf '#!/bin/bash\nREPORT=%q\nOWNER=%q\n' "$SESSION.preflight.txt" "$$"
        cat <<'PREFLIGHT_NOTICE'
printf '\033[H\033[2J'
printf '%s\n\n' 'Slay the Spire for RGDSplus'
printf '%s\n\n' '启动前检查失败，尚未释放游戏资源。'
cat "$REPORT"
printf '\n%s\n%s\n' '正版文件、缓存和存档未修改。' 'Runtime check failed before installation.'
printf '\n%s\n' "$REPORT"
for ((i=0; i<45; i++)); do
    kill -0 "$OWNER" 2>/dev/null || exit 0
    sleep 1
done
PREFLIGHT_NOTICE
    } >"$NOTICE_SCRIPT"
    chmod +x "$NOTICE_SCRIPT"
    if [ -x /usr/bin/weston-terminal ] &&
        [ -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ]; then
        /usr/bin/weston-terminal --fullscreen --font-size=20 --shell "$NOTICE_SCRIPT" >/dev/null 2>&1 &
        NOTICE_PID=$!
        # Use a bounded hold even if the terminal client delegates its window.
        sleep 45
    else
        echo "[preflight] firmware terminal unavailable; see $SESSION.preflight.txt"
    fi
}
