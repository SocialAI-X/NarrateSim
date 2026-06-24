# Reference Authenticity Audit

Audit date: 2026-05-25

Scope: `latex_paper/main.tex`, `latex_paper/sections/related_work.tex`, and all 56 entries in `latex_paper/bib/references.bib`.

Method: DOI entries were checked against DOI/Crossref metadata. ACL entries were cross-checked against ACL Anthology landing pages and exported BibTeX when available. Books/reports without DOI were checked against publisher, library, or official organization pages.

## Critical Findings

1. `sections/related_work.tex` is not currently included by `main.tex`. A fresh compile from the current source will omit the Related Work section and will leave 21 currently relevant bibliography entries uncited.
2. No clearly fabricated reference was found. Every bibliography entry is traceable to a DOI, official anthology page, publisher page, official report PDF, or library record.
3. `Asch2016` is real, but the local BibTeX metadata is problematic. The Routledge reprint has DOI `10.4324/9781315290614-27` and Crossref pages `315--323`; the current entry has no DOI and pages `295--303`. If you want the classic source instead, cite the 1951 Carnegie Press chapter in `Groups, Leadership, and Men`, pages `177--190`.
4. `Woolley2018` is real, but the DOI is missing. Add `doi = {10.1093/oso/9780190931407.001.0001}`.
5. `Graham2013` is real, but it is a book chapter in `Advances in Experimental Social Psychology`; the current `@article` type works passably in ACL style but is bibliographically imprecise. Prefer `@incollection`.
6. `main.aux`/`main.bbl` appear stale relative to the current `main.tex`: they still include Related Work citations even though `main.tex` no longer inputs that file. Rebuild after deciding whether to include Related Work.

## Entries With Recommended Metadata Fixes

| Key | Verdict | Issue | Suggested action | Evidence |
|---|---|---|---|---|
| `Asch2016` | Real but metadata wrong | Current pages `295--303` do not match the Routledge DOI metadata; DOI missing. | Use Routledge reprint: `doi={10.4324/9781315290614-27}`, `pages={315--323}`; or cite original 1951 Carnegie Press chapter `pages={177--190}`. | [Routledge book TOC](https://www.routledge.com/Organizational-Influence-Processes/Allen-Porter-Angle/p/book/9780765609991), [DOI](https://doi.org/10.4324/9781315290614-27), [classic 1951 record](https://cir.nii.ac.jp/crid/1570854175910469632) |
| `Woolley2018` | Real | DOI omitted. | Add `doi={10.1093/oso/9780190931407.001.0001}`. | [Oxford Academic](https://academic.oup.com/book/25859) |
| `Graham2013` | Real | Entry type is `@article`; DOI metadata identifies a book chapter. | Prefer `@incollection` with `booktitle={Advances in Experimental Social Psychology}`. | [DOI](https://doi.org/10.1016/B978-0-12-407236-7.00002-4) |
| `McGuire1964` | Real | DOI metadata title is shortened to "Some Contemporary Approaches"; local title is the fuller chapter title. | Keep title, but consider checking a publisher export before final submission. | [DOI](https://doi.org/10.1016/S0065-2601(08)60052-0) |
| `DaSanMartino2019` | Real | Crossref has singular "Article" and pages `5635--5645`; ACL Anthology has plural "Articles" and pages `5636--5646`. | Keep current ACL metadata. | [ACL Anthology](https://aclanthology.org/D19-1565) |

## Bibliography-Wide Authenticity Table

| Key | Status | Evidence / checked source | Notes |
|---|---|---|---|
| `Bratman1987` | Verified | [Open Library](https://openlibrary.org/books/OL2380135M/Intention_plans_and_practical_reason) | Title, author, Harvard University Press, 1987, ISBN match. |
| `Rao1995` | Verified | [AAAI record](https://aaai.org/papers/icmas95-042-bdi-agents-from-theory-to-practice/), [AAAI proceedings listing](https://aaai-24.aaai.org/Library/ICMAS/icmas95contents.php) | Title, authors, ICMAS 1995, starting page 312 match. |
| `Barabasi1999` | Verified | [DOI](https://doi.org/10.1126/science.286.5439.509) | Metadata matches. |
| `Plutchik1980` | Verified | [Google Books](https://books.google.com/books/about/Emotion.html?id=G5t9AAAAMAAJ), [Open Library](https://openlibrary.org/works/OL3942565W) | Title, author, Harper & Row, 1980, ISBN match. |
| `MohammadTurney2013` | Verified | [DOI](https://doi.org/10.1111/j.1467-8640.2012.00460.x) | DOI online year may show 2012; journal issue is 2013. |
| `Mohammad2018` | Verified | [DOI](https://doi.org/10.18653/v1/S18-1001) | Metadata matches. |
| `Zhang2024Sentiment` | Verified | [DOI](https://doi.org/10.18653/v1/2024.findings-naacl.246) | Metadata matches. |
| `Tu2023ChatGPT` | Verified | [DOI](https://doi.org/10.18653/v1/2023.findings-emnlp.813) | Metadata matches. |
| `GonzalezBailon2013` | Verified | [DOI](https://doi.org/10.1177/0002764213479371) | Metadata matches. |
| `Ecker2022` | Verified | [DOI](https://doi.org/10.1038/s44159-021-00006-y) | Metadata matches. |
| `Pennycook2021` | Verified | [DOI](https://doi.org/10.1016/j.tics.2021.02.007) | Metadata matches. |
| `Feinberg2019` | Verified | [DOI](https://doi.org/10.1111/spc3.12501) | Article number `e12501` is appropriate. |
| `FriedkinJohnsen1990` | Verified | [DOI](https://doi.org/10.1080/0022250X.1990.9990069) | Metadata matches; journal official title includes "The". |
| `Graham2013` | Verified with type issue | [DOI](https://doi.org/10.1016/B978-0-12-407236-7.00002-4) | Real book chapter, not a journal article. |
| `Lerner1980` | Verified | [DOI](https://doi.org/10.1007/978-1-4899-0448-5) | DOI title omits subtitle, but book identity matches. |
| `PennycookRand2019` | Verified | [DOI](https://doi.org/10.1016/j.cognition.2018.06.011) | Metadata matches; currently unused if Related Work remains omitted. |
| `StanovichWest2000` | Verified | [DOI](https://doi.org/10.1017/S0140525X00003435) | Metadata matches; currently unused if Related Work remains omitted. |
| `McGuire1964` | Verified with title nuance | [DOI](https://doi.org/10.1016/S0065-2601(08)60052-0) | Real chapter; Crossref title is shortened. |
| `Roozenbeek2019` | Verified | [DOI](https://doi.org/10.1057/s41599-019-0279-9) | Metadata matches. |
| `vanderLinden2017` | Verified | [DOI](https://doi.org/10.1002/gch2.201600008) | Metadata matches. |
| `EstebanRay1994` | Verified | [DOI](https://doi.org/10.2307/2951734) | JSTOR DOI metadata often lists only first page; local range is plausible. |
| `Witte1992` | Verified | [DOI](https://doi.org/10.1080/03637759209376276) | Metadata matches. |
| `Douglas2017` | Verified | [DOI](https://doi.org/10.1177/0963721417718261) | Metadata matches. |
| `Green2000` | Verified | [DOI](https://doi.org/10.1037/0022-3514.79.5.701) | Metadata matches. |
| `Cialdini2001` | Verified | [WorldCat](https://search.worldcat.org/es/title/influence-science-and-practice-4th-ed/oclc/948609742) | Title, author, 4th ed., Allyn and Bacon, 2001 match. |
| `Park2023` | Verified | [DOI](https://doi.org/10.1145/3586183.3606763) | Metadata matches; currently uncited if Related Work remains omitted. |
| `Deffuant2000` | Verified | [DOI](https://doi.org/10.1142/S0219525900000078) | Metadata matches. |
| `Flavell1979` | Verified | [DOI](https://doi.org/10.1037/0003-066X.34.10.906) | Metadata matches; currently unused if Related Work remains omitted. |
| `Walter2020` | Verified | [DOI](https://doi.org/10.1080/10584609.2019.1668894) | Online publication metadata may show 2019; journal issue is 2020. |
| `Mishler2001` | Verified | [DOI](https://doi.org/10.1177/0010414001034001002) | Metadata matches. |
| `Asch2016` | Verified with metadata error | [Routledge book](https://www.routledge.com/Organizational-Influence-Processes/Allen-Porter-Angle/p/book/9780765609991), [DOI](https://doi.org/10.4324/9781315290614-27) | Real chapter, but local pages/DOI should be fixed. |
| `Ferrara2016` | Verified | [DOI](https://doi.org/10.1145/2818717) | Metadata matches. |
| `Entman1993` | Verified | [DOI](https://doi.org/10.1111/j.1460-2466.1993.tb01304.x) | Metadata matches; currently uncited if Related Work remains omitted. |
| `BraddockDillard2016` | Verified | [DOI](https://doi.org/10.1080/03637751.2015.1128555) | Metadata matches; currently uncited if Related Work remains omitted. |
| `Tucker2018` | Verified | [DOI](https://doi.org/10.2139/ssrn.3144139) | SSRN DOI resolves; local institution field is acceptable. |
| `Wardle2017` | Verified | [Council of Europe PDF](https://rm.coe.int/information-disorder-report-2017/1680766412) | Official PDF confirms title, authors, DGI(2017)09, 2017. |
| `DaSanMartino2019` | Verified | [ACL Anthology](https://aclanthology.org/D19-1565) | Local ACL metadata is correct. |
| `liu-etal-2025-propainsight` | Verified | [ACL Anthology](https://aclanthology.org/2025.coling-main.376) | Metadata matches; no DOI in ACL export. |
| `otmakhova-frermann-2025-narrative` | Verified | [ACL Anthology](https://aclanthology.org/2025.findings-acl.477) | Metadata matches. |
| `sosnowski-etal-2025-dinam` | Verified | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1537) | ACL pages match local BibTeX. |
| `Woolley2018` | Verified with missing DOI | [Oxford Academic](https://academic.oup.com/book/25859) | Add DOI. |
| `Flache2017` | Verified | [DOI](https://doi.org/10.18564/jasss.3521) | Metadata matches. |
| `Bai2025` | Verified | [DOI](https://doi.org/10.1038/s41467-025-61345-5) | Metadata matches. |
| `Salvi2025` | Verified | [DOI](https://doi.org/10.1038/s41562-025-02194-6) | Metadata matches. |
| `pauli-etal-2025-measuring` | Verified | [ACL Anthology](https://aclanthology.org/2025.naacl-long.506) | Metadata matches. |
| `taubenfeld-etal-2024-systematic` | Verified | [ACL Anthology](https://aclanthology.org/2024.emnlp-main.16) | Metadata matches. |
| `choi-etal-2025-empirical` | Verified | [ACL Anthology](https://aclanthology.org/2025.findings-acl.265) | Metadata matches; currently uncited if Related Work remains omitted. |
| `wang-etal-2025-decoding` | Verified | [ACL Anthology](https://aclanthology.org/2025.coling-main.264) | Metadata matches; no DOI in ACL export. |
| `zhang-etal-2025-spark` | Verified | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1176) | ACL pages match local BibTeX. |
| `liu-etal-2025-mosaic` | Verified | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.325) | ACL pages match local BibTeX. |
| `liu-etal-2025-stepwise` | Verified | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1330) | ACL pages match local BibTeX. |
| `munker-etal-2026-dont` | Verified | [ACL Anthology](https://aclanthology.org/2026.eacl-long.51) | Metadata matches; 2026 EACL reference is real. |
| `maggini-etal-2026-partisanlens` | Verified | [ACL Anthology](https://aclanthology.org/2026.eacl-long.53) | Metadata matches; 2026 EACL reference is real. |
| `ma-etal-2026-open` | Verified | [ACL Anthology](https://aclanthology.org/2026.eacl-long.89) | Metadata matches; 2026 EACL reference is real. |
| `modzelewski-etal-2026-malicious` | Verified | [ACL Anthology](https://aclanthology.org/2026.eacl-long.144) | Metadata matches; 2026 EACL reference is real. |
| `borah-etal-2026-persuasion` | Verified | [ACL Anthology](https://aclanthology.org/2026.eacl-long.234) | Metadata matches; 2026 EACL reference is real. |

## Related Work Specific Check

All references cited in `sections/related_work.tex` are real and traceable. The highest-risk-looking items are the 2026 EACL papers, but they all resolve through ACL Anthology and DOI metadata. The main problem is not authenticity; it is inclusion. Because `main.tex` does not input the Related Work file, the paper source and compiled artifact can easily diverge.

If Related Work stays omitted, these otherwise valid entries will be uncited on a fresh compile: `Entman1993`, `BraddockDillard2016`, `Park2023`, `otmakhova-frermann-2025-narrative`, `sosnowski-etal-2025-dinam`, `Woolley2018`, `choi-etal-2025-empirical`, `wang-etal-2025-decoding`, `zhang-etal-2025-spark`, `liu-etal-2025-mosaic`, `liu-etal-2025-stepwise`, `munker-etal-2026-dont`, `maggini-etal-2026-partisanlens`, `ma-etal-2026-open`, `modzelewski-etal-2026-malicious`, `borah-etal-2026-persuasion`, plus unused general references `PennycookRand2019`, `StanovichWest2000`, `EstebanRay1994`, `Flavell1979`, and `Walter2020`.
