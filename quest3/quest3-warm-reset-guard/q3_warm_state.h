/* SPDX-License-Identifier: GPL-2.0 */
#ifndef Q3_WARM_STATE_H
#define Q3_WARM_STATE_H

struct q3_warm_state {
	bool owned;
	enum reboot_mode saved;
};

/* Only override the observed board default, never a foreign reset policy.
 * cmpxchg is required: a read followed by WRITE_ONCE could clobber a change.
 */
static int q3_warm_acquire(struct q3_warm_state *state)
{
	enum reboot_mode previous;

	if (state->owned)
		return -EBUSY;
	previous = cmpxchg(&reboot_mode, REBOOT_COLD, REBOOT_WARM);
	if (previous != REBOOT_COLD)
		return -EBUSY;
	state->saved = previous;
	state->owned = true;
	return 0;
}

/* Restore only if the value still matches the one this module installed.
 * This cannot detect another actor writing the identical WARM value (ABA).
 * No claim of global reset-policy ownership or reset success is made.
 */
static bool q3_warm_release(struct q3_warm_state *state)
{
	enum reboot_mode previous;

	if (!state->owned)
		return false;
	previous = cmpxchg(&reboot_mode, REBOOT_WARM, state->saved);
	state->owned = false;
	return previous == REBOOT_WARM;
}
#endif
