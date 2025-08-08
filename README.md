# Programmer Productivity Measurement

Created: July 11, 2025 5:21 PM
Labels & Language: CI&CD, GitHub, JIRA, Python
Source: https://github.com/prof-antar/devProductivity/tree/main

# Developer Productivity Evaluation

---

## Part 1 — Torque Clustering, Validation, and Future ML Models

> Is Torque Clustering a machine learning model?
> 

**In short:**

- **Torque Clustering itself:** no traditional training or test set is required.
- **For best results:** still need a *validation* set for parameter tuning, which is conceptually similar to testing.

### 1 Torque Clustering itself: no traditional training/test set

Torque Clustering is neither a supervised nor an unsupervised ML model; it is a **heuristic clustering algorithm**.

**What is a heuristic algorithm?**
It is a clearly defined, rule- and experience-based procedure. Given the same input data and parameters, it always produces exactly the same output. It does not *learn* patterns from data; it simply *executes* the rules you give it.

**The rules of Torque Clustering** are defined by three core parameters:

| Parameter | Meaning | Role |
| --- | --- | --- |
| **α (alpha)** | *Time weight* | Sensitivity to the time gap between commits |
| **β (beta)** | *Lines-of-code weight* | Sensitivity to the size of each code change |
| **gap** | *Torque threshold* | When the computed “torque” (time × code change) exceeds this value, a new batch is started |

Because the algorithm’s behavior is fully determined by these three values, there are no trainable weights or internal state. You don’t need a “training set” to teach it how to cluster.

### 2 Parameter tuning & validation: a de-facto “test”

Although no training is involved, not every parameter combination is good. To find the α, β, gap that best fit certain team or project, you tune them with a **validation set**.

The goal is to make the algorithm’s output batches match human developers’ idea of logical work units (e.g., “fix bug X”, “finish small feature Y”). The steps are:

**Step 1 – Build a ground truth**
Select a representative period (say, a week or a sprint) of commits.
Manually group them—using commit messages, Jira/Trello cards, and PR descriptions—into logical batches. This manual grouping is your **validation set**.

**Step 2 – Grid search**
Define parameter ranges, e.g.:

```
alpha: [0.0001, 0.0003, 0.001]
beta : [0.5, 1.0, 1.5]
gap  : [0.2, 0.3, 0.5]
```

Run Torque Clustering on the validation set for every combination.

**Step 3 – Evaluate clustering quality**
Compare machine-produced batches with your ground truth using standard metrics:

- **Adjusted Rand Index (ARI):** –1 to 1 (1 = perfect match, 0 = random).
- **Normalized Mutual Information (NMI):** 0 to 1 (1 = perfect).
- Homogeneity, Completeness, V-measure, etc.

**Step 4 – Pick the best parameters**
Choose the α, β, gap combination that yields the highest ARI or NMI.
Even without a strict `train_test_split`, creating a validation set and tuning parameters is effectively *testing* which rule set works best.

### 3 Future extensions: introduce training/test sets

Our current pipeline is a data-engineering and analysis flow that generates metrics. Once produced, those metrics become **features** for real ML models—at which point you *do* need training and test sets.

**Example use cases**

| Task | Goal | Features | Label | Process |
| --- | --- | --- | --- | --- |
| **Code-risk prediction** | Predict the probability that a batch introduces a bug | TBS (batch size), commits per batch, number of authors, files modified … | Whether the batch caused a hotfix | Split historical data into train/test, train a classifier (logistic regression, random forest), evaluate accuracy |
| **Cycle-time prediction** | Predict how long a Jira issue will take from start to finish | Issue type, priority, initial TBS … | Actual completion time | Train a regression model |
| **Developer-productivity anomaly detection** | Spot developers/teams with abnormal work patterns (may need help or are overworked) | Weekly TBS, Deploy Freq, CTL, … | — | Train an unsupervised model (e.g., Isolation Forest) on “normal” data, detect anomalies on new data |

## Part 2 — From Clustering to Evaluation on Batch Value

> What is the relationship between **Torque Clustering** and **measuring programmers’ productivity**?
> 

The project’s core objective is to **evaluate developer productivity**, and the very first step toward that goal is to **classify work units** (more precisely, to “cluster” them).

These two goals stand in a **“means vs. end”** relationship: clustering is the means, evaluation is the end.

### A Metaphor

> Imagine you’re evaluating the productivity of an automobile factory.
> 
> - **Individual Git commits** are like scattered **screws, parts, and steel plates** on the shop floor.
> - **Torque Clustering** is the factory’s **automated assembly line** that turns those parts into fully assembled **cars**.
> - **Developer-productivity evaluation** is the factory’s final **performance report**, telling you how many cars are built per day, how good they are, and how long each one takes.

**You can’t judge a factory’s efficiency by counting screws.** You must first **define a meaningful production unit**—**the “car”**—before measurement makes sense.

### 1 Why Not Evaluate Individual Commits Directly?

Judging productivity by individual commits is unreliable and misleading because commit granularity is inconsistent:

- One feature may span ten commits.
- A single commit might only fix a typo (`"fix typo"`).
- A commit could be unfinished work (`"WIP"`).
- A commit might even roll code back.

Tracking “commit count” encourages gaming the system. A developer could split one feature into 50 trivial commits, inflating numbers while polluting history. In summary, a single commit is “raw material,” not a “finished product”; evaluating it directly is meaningless.

### 2 The Role of Torque Clustering: Defining the “Finished Product”

Torque Clustering’s **sole purpose** is to intelligently group scattered commits into **meaningful, complete “logical work units”**—*batches*:

- A batch might be **one complete bug fix**.
- A batch might be **delivery of a small feature**.
- A batch might be **a complex refactor**.

Clustering transforms **“nuts and bolts” into “finished cars.”** It yields a **stable, reliable, meaningful object** for evaluation.

### 3 How Do We Evaluate the “Finished Product”?

After clustering, we can measure batches and derive true productivity indicators:

| Question about the car | Metric in our system | What it measures |
| --- | --- | --- |
| **How big/complex is the car?** | **TBS (Torque Batch Size)** | Code volume per batch |
| **How many cars per day?** | **Deploy Frequency** | Number of batches delivered per day |
| **How long does a car take?** | **CTL (Cycle/Lead Time)** | Time from start to finish for a batch |
| **How many cars need rework?** | **CSI (Change Failure Rate / Rework)** | Post-delivery fixes per batch |

Clustering is the prerequisite for meaningful evaluation: first define *what* to evaluate, then compute metrics to judge *how well* we’re doing. The project aims to shift from measuring **activity** (commit count) to measuring **outcomes** (valuable batches delivered).

## Part 3 — Evaluation on Batch Value: Different Batches, Different Value

**Each batch delivers entirely different “contribution” or “value.”** The system does not assume all batches are equal. Instead, it computes a **multi-dimensional profile** for each one:

### Layer 1 — Current Distinction of Batch Contribution

| Metric | Small-bug batch (example) | Heavy-feature batch (example) | Why it distinguishes |
| --- | --- | --- | --- |
| **TBS** | `15` lines | `800` lines | Directly reflects effort & complexity |
| **Commit count** | `1` | `12` | Features need many commits |
| **Files changed** | `2` | `25` | Features touch more modules |
| **Authors** | `1` | `3` | Complex features often collaborative |
| **Linked Jira issue** | `Bug` | `Story`/`Epic` | Issue type shows nature |
| **Jira story points** | `1` | `8` | Story points quantify value |
| **CTL** | `2 h` | `5 days` | Bug fixes quick, features long |

### Layer 2 — Toward Business Value

A 10-line **critical performance fix** may outweigh a 1,000-line **ordinary UI change**. 

To capture deeper value, add **qualitative** and **business-related** data:

1. **Jira/task fields:** issue type, priority, business-value score, customer impact.
2. **Code-quality & risk metrics:** cyclomatic complexity, coverage, defect density.
3. **Product & business KPIs:** DAU/MAU, conversion rate, performance metrics.

## Part 4 — Fair Developer Score (FDS)

### Mapping the **5 FDS Dimensions** to Real-World Data

| # | Dimension | What it captures | Concrete Metrics (min set) | Data Source & Extraction Notes | Formula / Query Sketch |
| --- | --- | --- | --- | --- | --- |
| 1 | **Throughput** | How much valuable work is shipped | • **Deploy Freq** – distinct successful pipeline runs (prod) per week• **% Batches On-Time** – batches merged before sprint end | - Git/CI: `commits`, `tags`, pipeline status- Sprint board: issue → sprint mapping | `sql SELECT COUNT(*)/weeks AS deploy_freq FROM ci_runs WHERE status='success'` |
| 2 | **Quality** | Defects & rework generated | • **Change Failure Rate** – hot-fix PRs ÷ total batches• **Defect Density** – confirmed bugs ÷ KLoC touched | - Issue tracker (`issue_type='Bug'`, `linked_pr`)- SonarQube coverage API + `git diff --stat` | CFR = `hotfix_batches / total_batches` |
| 3 | **Impact** | Business / technical value delivered | • **Story Points Closed** × Priority weight• **Business Value Score** (if present) | - Jira fields: `story_points`, `priority`, `customfield_business_value` | `Σ(sp * pri_weight)` where pri_weight ∈ {1,1.2,1.5,2} |
| 4 | **Efficiency** | Speed of turning work into shippable code | • **Median Cycle Time (CTL)** – PR open→merge• **Review Latency** – first review comment – PR open | - Git PR API timestamps- Review tool events | CTL = `P50(merge_ts - first_commit_ts)` |
| 5 | **Collaboration** | Healthy team interaction | • **Reviews Given/Received** per developer• **Co-authors per Batch** (git trailers) | - Git review database- `git show --pretty='%an %cN'` for co-authors | reviews_given = `COUNT(review_actions WHERE actor=user)` |

> Time window: rolling last 4 sprints (or 30 days) for all metrics before normalization.
> 
> 
> **Granularity**: compute per-developer records, then feed into the Z-score step described earlier.
> 

### **Fair Developer Score (FDS) — Mathematical Specification**
The **Fair Developer Score (FDS)** quantifies a developer’s contribution across batches of work by combining:

```
FDS = ∑ (Effort × Importance)  over all batches
```

---

### Part 1: Effort — How Much the Developer Pushed

```
Effort(u, b) = Share(u, b) × (
    0.25 × Z_scale +
    0.15 × Z_reach +
    0.20 × Z_centrality +
    0.20 × Z_dominance +
    0.15 × Z_novelty +
    0.05 × Z_speed
)
```

| Metric      | Description                                                                 |
|-------------|-----------------------------------------------------------------------------|
| **Share**   | Author’s proportion of effective churn in the batch                        |
| **Scale**   | log(1 + churn) – penalizes monster commits                                 |
| **Reach**   | Directory entropy – wider directory spread = higher score                  |
| **Centrality** | PageRank over co-change graph – importance of touched modules          |
| **Dominance** | Credit for starting, ending, and leading the batch                       |
| **Novelty** | Ratio of new lines (e.g., new files/APIs) to churn                         |
| **Speed**   | exp(–hours since previous commit / 24) – favors fast iteration             |

All metrics are **MAD-Z normalized** per repo × quarter and clipped to [−3, +3].

---

### Part 2: Importance — How Valuable the Batch Was

```
Importance(b) = 
    0.30 × Z_scale +
    0.20 × Z_scope +
    0.15 × Z_centrality +
    0.15 × Z_complexity +
    0.10 × Z_type +
    0.10 × Z_release_proximity
```

| Metric             | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| **Scale**          | log(1 + total churn) – entire batch size                                   |
| **Scope**          | Weighted blend: 0.5×files + 0.3×entropy + 0.2×unique dirs                   |
| **Centrality**     | PageRank score of modules touched in the batch                             |
| **Complexity**     | sqrt(unique_dirs) × log(1 + churn) – coordination overhead                 |
| **Type Priority**  | Importance inferred from commit type (see table below)                     |
| **Release Proximity** | exp(–days to nearest tag / 30) – urgency boost near releases           |

**Type Priority Weights:**

| Type         | Weight |
|--------------|--------|
| `security`   | 1.20   |
| `hotfix`     | 1.15   |
| `feature`    | 1.10   |
| `perf`       | 1.05   |
| `bugfix`     | 1.00   |
| `refactor`   | 0.90   |
| `other`      | 0.80   |
| `docs`       | 0.60   |

---

### Worked Example: Batch #1

**Effort Metrics (user-specific)**

| Metric      | Z-score |
|-------------|---------|
| Scale       | +0.67   |
| Reach       | +0.45   |
| Centrality  | –1.89   |
| Dominance   | 0.00    |
| Novelty     | +0.67   |
| Speed       | 0.00    |

 **Effort ≈ 0.47**

**Importance Metrics (batch-wide)**

| Metric          | Z-score |
|------------------|---------|
| Scale            | +1.28   |
| Scope            | +2.06   |
| Centrality       | –0.77   |
| Complexity       | +0.53   |
| Type Priority    | –0.58   |
| Release Proximity| –0.53   |

 **Importance ≈ 0.54**

**Final Contribution for Batch #1:**

```
Contribution = Effort × Importance ≈ 0.47 × 0.54 ≈ 0.26
```

---

### Standardization Notes

All raw metrics are normalized via:

- **MAD-Z transformation** per repo × quarter
- Clipping to [–3, +3] for outlier resistance
- Ensures fair comparison across diverse developers and teams
