# Large Language Models as Code Review Assistants: An Exploratory Case Study

Maria Fernanda Souza, John Peter Miller

Journal of Software Engineering Research, v. 14, n. 2, p. 45-67, 2025.
DOI: 10.1234/jser.2025.0042

> Note: this is a fictional sample article used to try out and test ACAM Assistant.

## Abstract

This study investigates how large language models (LLMs) can support code review in industrial software teams. We conducted an exploratory case study with two development teams over twelve weeks. Results indicate that LLM suggestions reduced median review time by 23% while reviewers rejected 41% of the generated comments as irrelevant. We conclude that LLM assistance is useful for routine checks but requires human judgment for design-level feedback.

Keywords: large language models; code review; software engineering; case study

## 1. Introduction

Code review is a central quality assurance practice in modern software development. However, reviews are time-consuming and reviewer attention is a scarce resource. Recent advances in large language models suggest that parts of the review process could be automated.

Few studies have examined LLM-assisted code review in industrial settings, and little is known about how developers perceive machine-generated review comments. This paper aims to explore how LLM assistance affects review time and review quality in practice.

The research questions are: RQ1: How does LLM assistance affect code review time? RQ2: How do developers perceive LLM-generated review comments?

## 2. Theoretical Framework

We build on the theory of distributed cognition, which frames code review as a joint cognitive activity shared between reviewers and their tools.

## 3. Methodology

We conducted an exploratory case study with two industrial teams totaling 18 developers. Data collection combined repository mining of 1,240 pull requests with semi-structured interviews with 12 developers. Quantitative data were analyzed with descriptive statistics and the Mann-Whitney U test, and interview transcripts were analyzed using thematic analysis.

## 4. Results

The median review time decreased from 5.2 hours to 4.0 hours after the introduction of the assistant, a reduction of 23%. Reviewers rejected 41% of the generated comments, mostly because they were considered irrelevant or already covered by linters. Interviews show that developers valued the assistant for detecting routine issues such as missing null checks.

## 5. Discussion

Our findings suggest that LLM assistance shifts reviewer effort from routine checks toward design discussions. A limitation of this study is its small sample of two teams from a single company, which limits generalizability.

## 6. Conclusion

LLM assistance can reduce code review time for routine issues, but human reviewers remain essential for design-level feedback. Future research should replicate this study across different organizations and programming languages.

## References

BACCHELLI, A.; BIRD, C. Expectations, outcomes, and challenges of modern code review. In: ICSE, 2013. p. 712-721.

HUTCHINS, E. Cognition in the Wild. Cambridge: MIT Press, 1995.
