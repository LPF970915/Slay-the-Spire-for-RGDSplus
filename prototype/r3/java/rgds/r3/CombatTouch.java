package rgds.r3;

import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardQueueItem;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.input.InputHelper;
import com.megacrit.cardcrawl.monsters.AbstractMonster;
import com.megacrit.cardcrawl.rooms.AbstractRoom;

/** Lower-panel gestures only; native playCard remains the sole commit path. */
public final class CombatTouch {
    public static AbstractCard card;
    public static AbstractMonster target;
    private static AbstractMonster presented;
    private static boolean presentedCard, pending;
    private static float offsetX, offsetY;
    private static final DragAim drag = new DragAim();
    private static UiTransform dragLayout;
    private static final float[][] boxes = new float[32][4];
    private static final AbstractMonster[] monsters = new AbstractMonster[32];
    private static long commits, cancels;
    private static final HandFocus handFocus = new HandFocus();

    public static boolean neutralHand(AbstractPlayer player) {
        if (!TouchInput.enabled) return false;
        boolean neutral = handFocus.neutral(AbstractDungeon.getCurrRoom(), TouchInput.padVersion,
                combat(player) && !player.hand.isEmpty());
        if (!neutral || !combat(player)) return false;
        if (!TouchInput.ownsPointer() && (player.hoveredCard != null || player.toHover != null)) {
            player.toHover = null;
            player.releaseCard();
        }
        return true;
    }

    private static boolean combat(AbstractPlayer player) {
        return CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                AbstractDungeon.getCurrRoom() != null &&
                AbstractDungeon.getCurrRoom().phase == AbstractRoom.RoomPhase.COMBAT &&
                !AbstractDungeon.getCurrRoom().isBattleOver && !AbstractDungeon.isScreenUp &&
                !CardCrawlGame.cardPopup.isOpen && !CardCrawlGame.relicPopup.isOpen &&
                !player.isDead;
    }

    private static boolean ready(AbstractPlayer player) {
        return combat(player) && !player.isEndingTurn && !player.endTurnQueued &&
                !AbstractDungeon.actionManager.turnHasEnded &&
                AbstractDungeon.actionManager.currentAction == null &&
                AbstractDungeon.actionManager.isEmpty() &&
                AbstractDungeon.actionManager.cardQueue.isEmpty();
    }

    private static boolean needsTarget() {
        return card != null && (card.target == AbstractCard.CardTarget.ENEMY ||
                card.target == AbstractCard.CardTarget.SELF_AND_ENEMY);
    }

    public static void cancel() {
        if (card != null) {
            cancels++;
            if (AbstractDungeon.player != null) AbstractDungeon.player.releaseCard();
            System.out.println("[r4-combat-touch] cancel count=" + cancels);
        }
        clear();
    }

    private static void clear() {
        card = null; target = presented = null;
        pending = presentedCard = false;
        drag.clear();
        dragLayout = null;
        java.util.Arrays.fill(monsters, null);
    }

    public static void committed() {
        CardFlight.queued(card, target, dragLayout);
        commits++;
        System.out.println("[r4-combat-touch] commit=" + commits + " card=" + card.cardID +
                " target=" + (target == null ? "none" : target.id));
        clear();
    }

    public static boolean aiming() {
        return card != null && drag.active && needsTarget() && target != null;
    }

    public static boolean selfAiming() {
        return card != null && drag.active && card.target == AbstractCard.CardTarget.SELF;
    }

    public static void displayed() {
        if (card != null) { presented = target; presentedCard = true; }
    }

    public static void diagnostics(java.util.Properties state) {
        state.setProperty("touch.card", card == null ? "" : card.cardID);
        state.setProperty("touch.target", target == null ? "" : target.id);
        state.setProperty("touch.targetIndex", Integer.toString(target == null || AbstractDungeon.getCurrRoom() == null
                ? -1 : AbstractDungeon.getCurrRoom().monsters.monsters.indexOf(target)));
        state.setProperty("touch.armed", Boolean.toString(card != null && drag.active));
        state.setProperty("touch.pending", Boolean.toString(pending));
        state.setProperty("touch.aimPolicy", "nearest-sticky-horizontal");
        if (card != null) {
            state.setProperty("touch.cardTarget", card.target.name());
            state.setProperty("touch.cardX", Float.toString(dragLayout.x(card.current_x)));
            state.setProperty("touch.cardY", Float.toString(768 - dragLayout.y(card.current_y)));
        }
        state.setProperty("touch.commits", Long.toString(commits));
        state.setProperty("touch.cancels", Long.toString(cancels));
        state.setProperty("touch.turn", Integer.toString(
                com.megacrit.cardcrawl.actions.GameActionManager.turn));
        if (AbstractDungeon.player != null && combat(AbstractDungeon.player)) {
            int i = 0;
            for (AbstractCard item : AbstractDungeon.player.hand.group) {
                DualRender.touchPosition(state, "touch.hand." + i, item.hb);
                state.setProperty("touch.hand." + i + ".id", item.cardID);
                state.setProperty("touch.hand." + i + ".angle", Float.toString(item.angle));
                state.setProperty("touch.hand." + i + ".targetAngle", Float.toString(item.targetAngle));
                state.setProperty("touch.hand." + i + ".hovered", Boolean.toString(
                        item == AbstractDungeon.player.hoveredCard));
                i++;
            }
            i = 0;
            for (AbstractMonster monster : AbstractDungeon.getCurrRoom().monsters.monsters) {
                state.setProperty("touch.monster." + i + ".x", Float.toString(monster.hb.cX));
                state.setProperty("touch.monster." + i + ".y", Float.toString(768 - monster.hb.cY));
                i++;
            }
        }
    }

    // 0: native input, 1: touch owns input, 2: caller invokes native playCard.
    public static int update(AbstractPlayer player) {
        if (!TouchInput.ownsPointer() || !combat(player)) {
            cancel();
            if (neutralHand(player) && !player.endTurnQueued && !player.isEndingTurn &&
                    !AbstractDungeon.actionManager.turnHasEnded) return 1;
            return 0;
        }
        // updateInput also drains the native end-turn request, not just card input.
        if (player.endTurnQueued || player.isEndingTurn || AbstractDungeon.actionManager.turnHasEnded) {
            cancel();
            return 0;
        }
        TouchState s = TouchInput.state;
        if (s.justDown) {
            cancel();
            if (ready(player)) {
                long last = -1;
                for (AbstractCard candidate : player.hand.group) {
                    long order = DualRender.touchOrder(candidate.hb, s.x, s.y);
                    if (order > last) { card = candidate; last = order; }
                }
                if (card != null) {
                    player.releaseCard();
                    dragLayout = UiTransform.hand(player.hand.size());
                    drag.begin(s.x, s.y);
                    offsetX = dragLayout.x(card.current_x) - s.x;
                    offsetY = dragLayout.y(card.current_y) - (768 - s.y);
                    System.out.println("[r4-combat-touch] down card=" + card.cardID);
                }
            }
        }
        // Prevent the original single-screen drag interpretation and stale pad selection.
        if (card == null) return 1;
        InputHelper.justClickedLeft = InputHelper.justReleasedClickLeft = false;
        if (!ready(player) || !player.hand.group.contains(card)) { cancel(); return 1; }
        if (target != null && (target.isDeadOrEscaped() || target.isDying ||
                !AbstractDungeon.getCurrRoom().monsters.monsters.contains(target))) {
            cancel();
            return 1;
        }
        if (!pending) {
            card.current_x = card.target_x = dragLayout.inverseX(s.x + offsetX);
            card.current_y = card.target_y = dragLayout.inverseY(768 - s.y + offsetY);
            card.angle = card.targetAngle = 0;
            card.targetDrawScale = .75f;
            int count = 0, previous = -1;
            for (AbstractMonster monster : AbstractDungeon.getCurrRoom().monsters.monsters) {
                if (monster.isDeadOrEscaped() || monster.isDying || count == boxes.length) continue;
                monsters[count] = monster;
                float[] b = boxes[count];
                b[0] = monster.hb.cX; b[1] = 768 - monster.hb.cY;
                b[2] = monster.hb.width; b[3] = monster.hb.height;
                if (target == monster) previous = count;
                count++;
            }
            boolean wasActive = drag.active;
            int index = drag.update(s.x, s.y, s.x + offsetX, 816 + s.y - offsetY,
                    boxes, count, previous);
            AbstractMonster next = index < 0 || !needsTarget() ? null : monsters[index];
            if (next != target || wasActive != drag.active) presentedCard = false;
            target = next;
        }
        player.hoveredCard = card;
        player.isDraggingCard = true;
        player.inSingleTargetMode = aiming();
        player.isHoveringDropZone = drag.active;
        if (s.justUp) {
            if (!drag.canRelease(s.x, s.y) ||
                    (needsTarget() && target == null)) { cancel(); return 1; }
            pending = true;
        }
        if (pending && presentedCard && presented == target) {
            if ((target != null && (target.isDeadOrEscaped() || target.isDying ||
                    !AbstractDungeon.getCurrRoom().monsters.monsters.contains(target))) ||
                    !card.canUse(player, target)) { cancel(); return 1; }
            for (CardQueueItem item : AbstractDungeon.actionManager.cardQueue)
                if (item.card == card) { cancel(); return 1; }
            return 2;
        }
        return 1;
    }
}
