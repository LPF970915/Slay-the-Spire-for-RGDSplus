package rgds;

import java.io.OutputStream;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.Properties;

/** Opt-in, read-only state snapshots for isolated device verification. */
public final class RuntimeProbe {
    private static final String DIRECTORY = System.getenv("RGDS_DIAGNOSTICS_DIR");
    private static long nextSample;
    private static boolean failed;

    private RuntimeProbe() {}

    private static Class<?> type(String suffix) throws ClassNotFoundException {
        return Class.forName("com.megacrit.cardcrawl." + suffix, false,
                Thread.currentThread().getContextClassLoader());
    }

    private static Object value(Object owner, String name) {
        if (owner == null) return null;
        Class<?> target = owner instanceof Class ? (Class<?>)owner : owner.getClass();
        for (Class<?> current = target; current != null; current = current.getSuperclass()) {
            try {
                Field field = current.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(owner instanceof Class ? null : owner);
            } catch (NoSuchFieldException missing) {
                // Fields of creatures and cards also live in their base classes.
            } catch (ReflectiveOperationException error) {
                return null;
            }
        }
        return null;
    }

    private static void copy(Properties state, String prefix, Object owner, String... fields) {
        if (owner == null) return;
        for (String field : fields) {
            Object data = value(owner, field);
            if (data != null) state.setProperty(prefix + field, String.valueOf(data));
        }
    }

    private static void cards(Properties state, String prefix, Object group) {
        Object data = value(group, "group");
        if (!(data instanceof List)) return;
        List<?> list = (List<?>)data;
        state.setProperty(prefix + "count", String.valueOf(list.size()));
        for (int i = 0; i < Math.min(list.size(), 20); i++)
            copy(state, prefix + i + ".", list.get(i), "name", "cardID", "costForTurn", "type");
    }

    public static void sample() {
        if (DIRECTORY == null || DIRECTORY.isEmpty() || failed) return;
        long now = System.nanoTime();
        if (now < nextSample) return;
        nextSample = now + 1_000_000_000L;
        try {
            Properties state = new Properties();
            state.setProperty("monotonicNs", String.valueOf(now));
            Class<?> game = type("core.CardCrawlGame");
            copy(state, "game.", game, "mode");
            copy(state, "menu.", value(game, "mainMenuScreen"), "screen");
            if ("GAMEPLAY".equals(state.getProperty("game.mode"))) {
                Class<?> dungeon = type("dungeons.AbstractDungeon");
                copy(state, "dungeon.", dungeon, "screen", "isScreenUp", "floorNum", "actNum");
                Object room = value(value(dungeon, "currMapNode"), "room");
                if (room != null) state.setProperty("room.class", room.getClass().getSimpleName());
                copy(state, "room.", room, "phase", "isBattleOver", "monstersEscaped");
                Object player = value(dungeon, "player");
                copy(state, "player.", player, "currentHealth", "maxHealth", "currentBlock",
                        "gold", "inSingleTargetMode", "isDraggingCard");
                copy(state, "hoveredCard.", value(player, "hoveredCard"), "name", "cardID", "costForTurn");
                copy(state, "hoveredMonster.", value(player, "hoveredMonster"), "name", "currentHealth");
                cards(state, "hand.", value(player, "hand"));
                for (String pile : new String[]{"drawPile", "discardPile", "exhaustPile"})
                    cards(state, pile + ".", value(player, pile));
                copy(state, "energy.", type("ui.panels.EnergyPanel"), "totalCount");
                Object monsters = value(value(room, "monsters"), "monsters");
                if (monsters instanceof List) {
                    List<?> list = (List<?>)monsters;
                    state.setProperty("monsters.count", String.valueOf(list.size()));
                    for (int i = 0; i < list.size(); i++)
                        copy(state, "monsters." + i + ".", list.get(i), "name", "currentHealth",
                                "maxHealth", "currentBlock", "intent", "isDead", "isDying");
                }
            }
            Path directory = Path.of(DIRECTORY);
            Files.createDirectories(directory);
            Path temporary = directory.resolve("state.xml.tmp");
            try (OutputStream stream = Files.newOutputStream(temporary)) {
                state.storeToXML(stream, "Read-only RGDS diagnostic snapshot", "UTF-8");
            }
            Files.move(temporary, directory.resolve("state.xml"), StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception error) {
            failed = true;
            System.err.println("[rgds-probe] disabled after snapshot failure: " + error);
        }
    }
}
