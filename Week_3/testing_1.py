
from collections import deque

import importlib

ticket_data = importlib.import_module("ticket_data_testing")

TICKETS = ticket_data.TICKETS
SUPPORTED_CATEGORIES = ticket_data.SUPPORTED_CATEGORIES

try:
    ticket_display = importlib.import_module("ticket_display")
except ModuleNotFoundError:
    ticket_display = importlib.import_module("Ticket_Display")

display_tickets = ticket_display.display_tickets
display_state = ticket_display.display_state


def _ticket_id(record):
	"""Return the identifier from a ticket record."""
	return record["ticket_id"] if "ticket_id" in record else record["id"]


def build_registry(records):
	"""Return independent ticket records indexed by unique ID."""
	registry = {}
	for record in records:
		ticket_id = _ticket_id(record)
		if ticket_id in registry:
			raise ValueError(f"Duplicate ticket ID: {ticket_id!r}")
		registry[ticket_id] = dict(record)
	return registry


def scan_lookup(records, ticket_id):
	"""Return the first matching ticket, or None when absent."""
	for record in records:
		if _ticket_id(record) == ticket_id:
			return record
	return None


def indexed_lookup(registry, ticket_id):
	"""Return the matching live ticket, or None when absent."""
	return registry.get(ticket_id)


def update_priority(registry, ticket_id, priority):
	"""Update one existing ticket's priority and report whether it was found."""
	if ticket_id not in registry:
		return False
	registry[ticket_id]["priority"] = priority
	return True


def filter_by_category(registry, category):
	"""Return independent copies of tickets matching the selected category."""
	return [
		dict(record)
		for record in registry.values()
		if record.get("category") == category
	]


def enqueue_ticket(state, ticket_id):
	"""Queue a known open ticket once, returning whether it was accepted."""
	registry = state["registry"]
	if ticket_id not in registry:
		return False
	if str(registry[ticket_id].get("status", "")).lower() != "open":
		return False
	if ticket_id in state["pending"]:
		return False
	state["pending"].append(ticket_id)
	return True


def process_next(state):
	"""Complete the oldest waiting ticket and remember its previous status."""
	while state["pending"]:
		ticket_id = state["pending"].popleft()
		ticket = state["registry"].get(ticket_id)
		if ticket is not None and str(ticket.get("status", "")).lower() == "open":
			break
	else:
		return None
	state["undo"].append(
		{"ticket_id": ticket_id, "previous_status": ticket["status"]}
	)
	ticket["status"] = "completed"
	return ticket_id


def undo_process(state):
	"""Restore the latest processed ticket and return it to the queue front."""
	if not state["undo"]:
		return None
	action = state["undo"].pop()
	ticket_id = action["ticket_id"]
	state["registry"][ticket_id]["status"] = action["previous_status"]
	state["pending"].appendleft(ticket_id)
	return ticket_id


def repair_queue(registry, pending):
	"""Return a new queue of known IDs and a list of removed missing IDs."""
	repaired = deque()
	removed = []
	for ticket_id in pending:
		if ticket_id in registry:
			repaired.append(ticket_id)
		else:
			removed.append(ticket_id)
	return repaired, removed


def cancel_ticket(state, ticket_id):
	"""Remove an open ticket and any waiting request, leaving history unchanged."""
	registry = state["registry"]
	if ticket_id not in registry:
		return False
	if str(registry[ticket_id].get("status", "")).lower() != "open":
		return False
	del registry[ticket_id]
	state["pending"], _ = repair_queue(registry, state["pending"])
	return True


def main():
	"""Demonstrate registry, queue processing, undo, repair, and cancellation."""
	registry = build_registry(TICKETS)
	if not registry:
		print("No tickets are available.")
		return

	first_id = next(iter(registry))
	scanned = scan_lookup(TICKETS, first_id)
	indexed = indexed_lookup(registry, first_id)
	print("Scan and indexed lookup agree:", scanned == indexed)
	print("Found ticket:", indexed)

	old_priority = registry[first_id].get("priority")
	new_priority = "High" if str(old_priority).lower() != "high" else "Low"
	print("Priority updated:", update_priority(registry, first_id, new_priority))

	category = next(
		(
			value for value in SUPPORTED_CATEGORIES
			if any(record.get("category") == value for record in registry.values())
		),
		None,
	)
	selection = filter_by_category(registry, category) if category is not None else []
	print("Selected tickets:")
	display_tickets("Selected tickets", selection)

	state = {"registry": registry, "pending": deque(), "undo": []}
	open_ids = [
		ticket_id for ticket_id, ticket in registry.items()
		if str(ticket.get("status", "")).lower() == "open"
	]
	for ticket_id in open_ids[:2]:
		print("Queued:", ticket_id, enqueue_ticket(state, ticket_id))
	if open_ids:
		print("Duplicate request rejected:", not enqueue_ticket(state, open_ids[0]))
	print("Unknown request rejected:", not enqueue_ticket(state, "__unknown_ticket__"))
	for _ in range(min(2, len(open_ids))):
		print("Processed:", process_next(state))
	print("After processing:")
	display_state("After processing", state)
	print("Undo:", undo_process(state))
	display_state("After undo", state)

	stale_queue = deque([*state["pending"], "__missing_ticket__"])
	state["pending"], removed = repair_queue(registry, stale_queue)
	print("Removed stale IDs:", removed)

	cancel_id = next(
		(
			ticket_id for ticket_id, ticket in registry.items()
			if str(ticket.get("status", "")).lower() == "open"
		),
		None,
	)
	if cancel_id is not None:
		print("Open ticket cancelled:", cancel_ticket(state, cancel_id))
	print("Missing cancellation rejected:", not cancel_ticket(state, "__unknown_ticket__"))
	print("Saved selection (independent copies):")
	display_tickets("Saved selection (independent copies)", selection)
	print("Current tickets:")
	display_tickets("Current tickets", list(registry.values()))
	display_state("Current state", state)


if __name__ == "__main__":
	main()