package rgds.r3;

import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.screens.mainMenu.MainMenuScreen;
import com.megacrit.cardcrawl.screens.mainMenu.MenuPanelScreen.PanelScreen;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

/** Opt-in gallery navigation, executed once on the native game update thread. */
public final class PageProbe {
    private static final boolean enabled = "1".equals(System.getenv("RGDS_R4_PAGE_PROBE")) || ReviewProbe.enabled;
    private static long nextPoll;

    public static void poll() {
        ReviewProbe.tick();
        if (!enabled || System.nanoTime() < nextPoll) return;
        nextPoll = System.nanoTime() + 250_000_000L;
        Path directory = Path.of(System.getenv("RGDS_DIAGNOSTICS_DIR"));
        Path request = directory.resolve("page.request");
        if (!Files.isRegularFile(request)) return;
        String command = "";
        String outcome;
        try {
            if (Files.size(request) > 64) throw new IllegalArgumentException("Oversized request");
            command = Files.readString(request).trim();
            Files.delete(request);
            if (command.matches("u\\d\\d")) {
                ReviewProbe.open(command);
            } else if (command.equals("map") || command.equals("deck") || command.equals("settings")) {
                if (CardCrawlGame.mode != CardCrawlGame.GameMode.GAMEPLAY ||
                        AbstractDungeon.player == null || AbstractDungeon.isScreenUp ||
                        AbstractDungeon.screen != AbstractDungeon.CurrentScreen.NONE ||
                        Boolean.TRUE.equals(DualRender.get(AbstractDungeon.player, "inSingleTargetMode")) ||
                        Boolean.TRUE.equals(DualRender.get(AbstractDungeon.player, "isDraggingCard")))
                    throw new IllegalStateException("Passive game page requires idle gameplay with no modal or targeting");
                if (command.equals("map")) AbstractDungeon.dungeonMapScreen.open(false);
                if (command.equals("deck")) AbstractDungeon.deckViewScreen.open();
                if (command.equals("settings")) AbstractDungeon.settingsScreen.open();
            } else {
                MainMenuScreen menu = CardCrawlGame.mainMenuScreen;
                if (CardCrawlGame.mode != CardCrawlGame.GameMode.CHAR_SELECT || menu == null ||
                        menu.screen != MainMenuScreen.CurScreen.MAIN_MENU ||
                        menu.isSettingsUp || CardCrawlGame.cardPopup.isOpen || CardCrawlGame.relicPopup.isOpen)
                    throw new IllegalStateException("Return to main menu using native controls first");
                if (!java.util.Arrays.asList("cards", "relics", "potions", "stats", "history",
                        "custom", "character", "inputs", "patch", "credits").contains(command))
                    throw new IllegalArgumentException("Unknown gallery page");
                menu.hideMenuButtons();
                menu.darken();
                // Native B returns to this panel. Its controller list must exist
                // even when a screenshot probe bypasses the normal parent click.
                PanelScreen parent = command.equals("cards") || command.equals("relics") ||
                        command.equals("potions") ? PanelScreen.COMPENDIUM :
                        command.equals("stats") || command.equals("history") ? PanelScreen.STATS :
                        command.equals("character") || command.equals("custom") ? PanelScreen.PLAY :
                        PanelScreen.SETTINGS;
                menu.panelScreen.open(parent);
                // No arbitrary class names, room replacement, rewards or game-ending constructors.
                switch (command) {
                    case "cards": menu.cardLibraryScreen.open(); break;
                    case "relics": menu.relicScreen.open(); break;
                    case "potions": menu.potionScreen.open(); break;
                    case "stats": menu.statsScreen.open(); break;
                    case "history": menu.runHistoryScreen.open(); break;
                    case "custom": menu.customModeScreen.open(); break;
                    case "character": menu.charSelectScreen.open(false); break;
                    case "inputs": menu.inputSettingsScreen.open(); break;
                    case "patch": menu.patchNotesScreen.open(); break;
                    case "credits": menu.creditsScreen.open(false); break;
                    default: throw new IllegalArgumentException("Unknown gallery page");
                }
            }
            outcome = "opened";
        } catch (Exception error) {
            outcome = "rejected: " + error.getClass().getSimpleName() + ": " + error.getMessage();
            try { Files.deleteIfExists(request); } catch (Exception ignored) { }
        }
        try {
            Path temp = directory.resolve("page-result.tmp");
            Files.writeString(temp, command + "\n" + outcome + "\nsource=" +
                    (command.startsWith("u") ? "isolated-native-ui-specimen" : "native-api-probe") +
                    "\nphysical_verified=false\n");
            Files.move(temp, directory.resolve("page-result.txt"), StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception error) {
            System.err.println("[r4-probe] result write failed: " + error);
        }
        System.out.println("[r4-probe] " + command + " " + outcome);
    }
}
