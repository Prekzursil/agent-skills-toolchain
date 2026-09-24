# Supervisor outreach — how to use the one-page research profile

Decision **G-16**. Companion to `Andrei-Mihai_Visalon_research_profile_onepage.pdf`.

> **Provenance note.** G-1, G-2, G-3, G-6 and G-18 are recorded in `profile.yaml`
> `x_decisions`. **G-16 is not** — it exists only in the session decision log.
> *TODO-CONFIRM: write G-16 into `profile.yaml` `x_decisions` so the outreach plan has
> the same durability as the rest.*

---

## The situation, stated plainly

- The doctorate is **committed** (G-1): UB Doctoral School of Informatics, July 2027
  concurs.
- The binding gate is a **supervisor's written agreement**. The publication list is
  optional and only a tie-break. So the scarce resource is not papers — it is a
  supervisor's attention and then their signature.
- Low-value publications are rejected (G-18: SemEval-2027 is skipped). That means the
  outreach cannot lean on "I will have N more papers by July". It has to lean on what is
  already checkable.
- Timeline: outreach **December**, concurs **July 2027**. Roughly seven months. That is
  enough time to do one substantial piece of work *with* a supervisor, and not enough to
  rescue a cold start in June.

---

## 1. The opening ask: arXiv endorsement

**Do not open with "will you supervise me".** That asks a stranger for a multi-year
commitment in a first email, and the default answer to a multi-year commitment from a
stranger is no.

Open with a **small, specific, bounded favour that is useful on its own**: ask them to
**endorse you for the relevant arXiv category** (`cs.CL`, and/or `cs.LG`) so you can post
the GRACE technical report and the manuscript in preparation.

Why this works, concretely:

- arXiv requires an endorsement for a first submission to a category when the submitter
  has no prior qualifying submission from a recognised institution. It is a real gate,
  and asking to clear it is a real question, not a pretext.
- It costs the endorser a few minutes and no commitment. It is easy to say yes to.
- It **forces them to look at the work** — an endorser is asked to judge whether the
  person is capable of producing work appropriate to the category. That is exactly the
  judgement you want them to make, and they will make it against the one-page profile.
- It creates a correspondence thread that exists for a legitimate reason, so the
  supervision question becomes a follow-up between two people who have already
  exchanged mail, not a cold approach.
- If they endorse and the preprint goes up, you gain a citable, timestamped artefact
  before July — without publishing anything low-value (G-18 stays intact).

**Shape of the first email** (short — five or six sentences, no attachments beyond the
one-page PDF):

1. Who you are in one line: master's student at FMI, working on evaluation methodology
   for clinical and multilingual NLP.
2. The concrete thing you built, with the number: the GRACE @ IberLEF 2026 Track 1
   benchmark — 27 runs, nine encoders, three seeds, ensemble at 0.743 dev strict
   macro-F1 against 0.705 for the best backbone averaged over three seeds (best
   individual run 0.737), chosen without dev-set model selection.
3. The ask: would they be willing to endorse you for `cs.CL` so the technical report can
   be posted.
4. One sentence that the profile is attached and that you are exploring doctoral
   supervision for the July 2027 concurs — signalled, not asked.
5. Offer to send the code and the artefact manifest.

**Never** send the profile while it still shows `TODO-CONFIRM` markers. See
`TEMPLATE.md` → *Before this is sent to anyone*.

---

## 2. Aligning the dissertation topic

The profile's last section deliberately ends on an open TODO: *the dissertation topic is
to be agreed with a supervisor, not declared to one.* Keep it that way. Arriving with a
fixed topic tells a supervisor you want a signature, not a supervisor.

What the profile **does** commit to is a **direction**, which is the part that has to
align: turning the GRACE evaluation protocol into a general method for separating a
genuine modelling gain from a selection effect in clinical and biomedical language
processing, with every run, seed and artefact released under a checksummed manifest.

That direction is deliberately shaped to bend three ways without breaking:

| If the group works on… | The direction becomes… | What already evidences it |
|---|---|---|
| Clinical / biomedical NLP | Evaluation methodology **for their task and their corpora** | GRACE (Spanish/multilingual clinical encoders, 27 runs, 3 seeds) |
| ML methodology, benchmarking, reproducibility | Selection effects and reporting protocols **as the object of study** | no dev-set model selection; the multi-seed design; the Zenodo SHA-256 manifest |
| Pharmacovigilance / health data | Signal analysis **with the same evaluation discipline applied to it** | the FAERS / phenibut work — **once it is documented** (currently `TODO-CONFIRM`) |

Before the first email, do this once per target: read their **two most recent papers**
and write **one sentence** naming a specific methodological problem in their work that
your direction touches. One sentence. If you cannot write it honestly, they are the
wrong target — drop them and pick another. That sentence is the difference between a
mass mail and a real approach, and a supervisor can tell in three seconds.

---

## 3. Why two candidate supervisors, not one

**Approach exactly two. Not one, and not eight.**

Against **one**:

- A single target makes the entire doctorate a single point of failure on one person's
  workload, sabbatical, funding or mood. A no in February leaves no time to recover
  before July.
- It also distorts the conversation: when you have no alternative, you concede on topic,
  on scope and on terms. Having a second live conversation is what lets you say "that
  direction is not what I want to spend three years on" — which is the one thing that
  actually predicts finishing.

Against **many**:

- The per-target cost is the honest part — the two-papers read and the one specific
  sentence. That does not scale, and a generic mail is worse than no mail: it is
  legible as generic, and Romanian informatics faculties are small enough that the
  recipients talk to each other.
- Asking several people in one department for an arXiv endorsement in the same week
  looks exactly like what it is.

**Two** is the smallest number that gives redundancy while keeping every approach
genuinely specific. Practical rules:

- Prefer **two different groups or research directions**, not two people at one desk.
  Two doors, not one door twice.
- **Stagger them**: send the first, wait about ten working days, then send the second.
  Simultaneous mail to close colleagues is discovered and reads as shopping.
- **Be honest if asked** whether you are speaking to anyone else. "I am talking to two
  people whose work fits, and I will tell you before I commit anywhere" is a normal,
  respectable answer. Concealing it and being found out is fatal.
- **Owner picks the people** (G-1 explicitly reserves this). This note is the method,
  not the shortlist.
- *TODO-CONFIRM: the two names, their groups, and the one-sentence alignment for each.*

---

## Sequence

| When | Action |
|---|---|
| Before anything | Close the `TODO-CONFIRM` list in `TEMPLATE.md`. Fix ORCID and unsuppress the link. |
| Early December | Target 1: endorsement ask + the one-page profile. |
| +10 working days | Target 2, same shape, different alignment sentence. |
| On any reply | Offer the code and the artefact manifest. Propose a 20-minute call. Do not send a CV unless it is asked for — this is a research profile, not a job application. |
| At the call | Ask what *they* would want the topic to be. Listen first. Bring the direction, not a plan. |
| By March | A written expression of intent from one of them. That is the real deadline; July is only the paperwork. |
