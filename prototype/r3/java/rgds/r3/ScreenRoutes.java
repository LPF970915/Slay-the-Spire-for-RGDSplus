package rgds.r3;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** Explicit page inventory. Unlisted mod pages retain the lower-screen fallback. */
public final class ScreenRoutes {
    public static final Map<String, String> LOWER;
    public static final Map<String, String> MIRROR;
    public static final Map<String, String> UPPER;
    public static final Map<String, String> DUNGEON;
    public static final Map<String, String> MENU;
    static {
        Map<String, String> lower = new LinkedHashMap<String, String>();
        add(lower, "U02", "screens.mainMenu.MenuPanelScreen");
        add(lower, "U03", "screens.mainMenu.SaveSlotScreen", "ui.panels.RenamePopup",
                "ui.panels.DeleteSaveConfirmPopup");
        add(lower, "U05", "screens.custom.CustomModeScreen");
        add(lower, "U13", "screens.MasterDeckViewScreen", "screens.DrawPileViewScreen",
                "screens.DiscardPileViewScreen", "screens.ExhaustPileViewScreen");
        add(lower, "U14", "screens.select.HandCardSelectScreen");
        add(lower, "U15", "screens.select.GridCardSelectScreen");
        add(lower, "U18", "screens.CardRewardScreen");
        add(lower, "U17", "screens.CombatRewardScreen");
        add(lower, "U19", "screens.select.BossRelicSelectScreen");
        add(lower, "U20", "shop.ShopScreen", "shop.Merchant");
        add(lower, "U22", "rooms.CampfireUI");
        add(lower, "U26", "screens.options.SettingsScreen", "screens.options.InputSettingsScreen",
                "screens.options.OptionsPanel");
        add(lower, "U27", "ui.FtueTip", "screens.options.ConfirmPopup",
                "screens.mainMenu.EarlyAccessPopup", "screens.mainMenu.SyncMessage");
        add(lower, "U29", "screens.compendium.CardLibraryScreen",
                "screens.compendium.RelicViewScreen", "screens.compendium.PotionViewScreen");
        add(lower, "U30", "screens.stats.StatsScreen", "screens.runHistory.RunHistoryScreen");
        add(lower, "U31", "screens.mainMenu.PatchNotesScreen");
        add(lower, "U32", "daily.DailyScreen", "screens.leaderboards.LeaderboardScreen");
        LOWER = Collections.unmodifiableMap(lower);
        Map<String, String> mirror = new LinkedHashMap<String, String>();
        add(mirror, "U07", "screens.DungeonMapScreen");
        add(mirror, "U23", "rewards.chests.AbstractChest");
        add(mirror, "U28", "screens.DoorUnlockScreen");
        add(mirror, "U31", "credits.CreditsScreen");
        MIRROR = Collections.unmodifiableMap(mirror);
        Map<String, String> upper = new LinkedHashMap<String, String>();
        add(upper, "U01", "screens.splash.SplashScreen", "screens.DungeonTransitionScreen");
        add(upper, "U04", "screens.charSelect.CharacterSelectScreen");
        add(upper, "U06", "neow.NeowEvent", "cutscenes.NeowNarrationScreen");
        add(upper, "U21", "events.GenericEventDialog", "events.RoomEventDialog");
        add(upper, "U24", "ui.panels.TopPanel");
        add(upper, "U12", "ui.panels.PotionPopUp");
        add(upper, "U25", "screens.SingleCardViewPopup", "screens.SingleRelicViewPopup");
        add(upper, "U28", "screens.DeathScreen", "screens.VictoryScreen",
                "unlock.UnlockCharacterScreen", "neow.NeowUnlockScreen");
        UPPER = Collections.unmodifiableMap(upper);
        Map<String, String> dungeon = new LinkedHashMap<String, String>();
        states(dungeon, "U33", "NONE", "NO_INTERACT");
        states(dungeon, "U13", "MASTER_DECK_VIEW", "GAME_DECK_VIEW", "DISCARD_VIEW", "EXHAUST_VIEW");
        states(dungeon, "U26", "SETTINGS", "INPUT_SETTINGS");
        states(dungeon, "U15", "GRID", "TRANSFORM");
        states(dungeon, "U07", "MAP");
        states(dungeon, "U27", "FTUE");
        states(dungeon, "U16", "CHOOSE_ONE");
        states(dungeon, "U14", "HAND_SELECT");
        states(dungeon, "U20", "SHOP");
        states(dungeon, "U17", "COMBAT_REWARD");
        states(dungeon, "U18", "CARD_REWARD");
        states(dungeon, "U19", "BOSS_REWARD");
        states(dungeon, "U28", "DEATH", "VICTORY", "UNLOCK", "DOOR_UNLOCK", "NEOW_UNLOCK");
        states(dungeon, "U31", "CREDITS");
        DUNGEON = Collections.unmodifiableMap(dungeon);
        Map<String, String> menu = new LinkedHashMap<String, String>();
        states(menu, "U02", "MAIN_MENU", "PANEL_MENU");
        states(menu, "U03", "SAVE_SLOT");
        states(menu, "U04", "CHAR_SELECT");
        states(menu, "U05", "CUSTOM");
        states(menu, "U06", "NEOW_SCREEN");
        states(menu, "U13", "BANNER_DECK_VIEW");
        states(menu, "U29", "CARD_LIBRARY", "RELIC_VIEW", "POTION_VIEW");
        states(menu, "U26", "SETTINGS", "INPUT_SETTINGS");
        states(menu, "U27", "ABANDON_CONFIRM");
        states(menu, "U30", "STATS", "RUN_HISTORY");
        states(menu, "U31", "CREDITS", "PATCH_NOTES");
        states(menu, "U32", "DAILY", "TRIALS", "LEADERBOARD");
        states(menu, "U28", "DOOR_UNLOCK");
        states(menu, "U33", "NONE");
        MENU = Collections.unmodifiableMap(menu);
    }

    private static void states(Map<String, String> map, String id, String... names) {
        for (String name : names) {
            if (map.put(name, id) != null) throw new IllegalArgumentException("Duplicate state " + name);
        }
    }

    public static String roomId(String name) {
        if (name.startsWith("MonsterRoom")) return "U08";
        if (name.equals("EventRoom")) return "U21";
        if (name.equals("ShopRoom")) return "U20";
        if (name.equals("RestRoom")) return "U22";
        if (name.startsWith("TreasureRoom")) return "U23";
        if (name.equals("NeowRoom")) return "U06";
        if (name.equals("VictoryRoom") || name.equals("TrueVictoryRoom")) return "U28";
        return "U33";
    }

    public static String dungeonId(String state, String room) {
        return state.equals("NONE") ? roomId(room) : DUNGEON.getOrDefault(state, "U33");
    }

    public static boolean previewPage(String id) {
        return java.util.Arrays.asList("U13", "U14", "U15", "U16", "U18", "U19",
                "U20", "U25", "U28", "U29", "U30").contains(id);
    }

    private static void add(Map<String, String> map, String id, String... classes) {
        for (String name : classes) map.put("com.megacrit.cardcrawl." + name, id);
    }

    public static String id(String name) {
        String id = LOWER.get(name);
        if (id == null) id = MIRROR.get(name);
        if (id == null) id = UPPER.get(name);
        return id;
    }

    public static boolean knownRoom(String name) {
        return name.startsWith("MonsterRoom") || name.equals("EventRoom") ||
                name.equals("ShopRoom") || name.equals("RestRoom") ||
                name.startsWith("TreasureRoom") || name.equals("EmptyRoom") ||
                name.equals("TrueVictoryRoom") || name.equals("VictoryRoom") || name.equals("NeowRoom");
    }
}
