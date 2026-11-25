# Proposal: how we record adjudication decisions

**From Team C, 2026-11-04. Draft for the Team A and B delegates. Not agreed.**

## The problem

When two reviewers disagree, someone has to decide the final answer. All three
teams must keep both original answers and store that decision separately.

The shared `adjudications` table can't do this yet. It doesn't say which
answers a decision settles, and nothing stops someone editing or deleting a
decision. Team C needs this now, so we'd like one shared design rather than
three.

## The idea

Each decision is a new record that says:

- **what** was decided (a clip, or for Team C one viewer answer on one field);
- **which original answers** it settles (at least two);
- **the final answer**;
- **who decided**: someone who wasn't one of the original reviewers;
- **how**: by discussion, a third reviewer, or a pre-agreed rule;
- **why**: a short reason;
- **when**, and which codebook or protocol version applied.

Four ground rules:

1. Decisions are never edited or deleted. To fix one, add a new decision that
   points to the old one.
2. Only real disagreements get a decision. If reviewers agree, their answer
   stands.
3. Agreement scores always use the original answers, never the decisions.
4. Decisions are exported separately from the original answers.

## Questions for you

1. One shared table for all teams, or one per team with the same columns?
2. Should someone who reviewed the item be barred from deciding it?
3. Do visual and audio review need any other way of deciding?
4. Do `UNSURE` answers need a decision, or are they left out?
5. Who updates the existing shared table? It's empty in the public demo.

Until we agree, Team C won't touch the shared table. Afterwards we'll build our
version first and share the code, so Teams A and B can reuse it.
