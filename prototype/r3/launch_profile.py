"""R3-only launcher overrides; never edit the stable single-screen launcher."""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Stable launcher changed: missing/ambiguous R3 override")
    return text.replace(old, new, 1)


def configure(text):
    text = replace_once(text, '    "-javaagent:$APP_DIR/rgds-input-agent.jar"',
                        '    "-javaagent:$APP_DIR/rgds-input-agent.jar"\n'
                        '    "-javaagent:$APP_DIR/rgds-dual-r3.jar"')
    text = replace_once(text, '$APP_DIR/librgds-sdl.so:$APP_DIR/libwrap.so',
                        '$APP_DIR/librgds-dual.so:$APP_DIR/libwrap.so')
    text = replace_once(text, "printf '1024\\n768\\n24\\nfalse\\ntrue\\nfalse\\n'",
                        "printf '1024\\n768\\n%s\\nfalse\\ntrue\\nfalse\\n' \"${RGDS_R3_FPS:-30}\"")
    text = replace_once(text, '    "-XX:+UseSerialGC"',
                        '    "-XX:+Use${RGDS_R3_GC:-Serial}GC"\n'
                        '    "-XX:TieredStopAtLevel=${RGDS_R4_JIT_TIER:-4}"\n'
                        '    "-Xlog:gc*,safepoint:file=$SESSION.gc.log:uptimemillis,level,tags:filecount=2,filesize=2M"')
    text = replace_once(text, '    "-Xms128M"', '    "-Xms${RGDS_R3_XMS:-64}M"')
    return text
