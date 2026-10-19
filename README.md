## LLM-noise-prompt-test

We are studying the robustness of LLMs to typos and noise.

Proposed metrics + automatic benchmark design: see `BENCHMARK.md`
(reference implementation of the metrics: `noisebench.py`, run with `--demo`).

## task:

### 1  
Create a text processor that applies the following transformations based on checkboxes:  
- Swap two adjacent letters  
- Delete a letter  
- Insert a space  

Include a global slider controlling the percentage of modifications relative to the total number of characters.

### 2  
Design four test prompts: two short and two medium-length ones.  
Two from them should instruct the model to generate code, allowing visual verification of its understanding; the other two should require direct answers.  

Choose programs that are concise in implementation yet sufficiently non-trivial to demonstrate comprehension—avoiding overly simplistic or template-like examples, while remaining solvable by models such as Gemma 4 and Qwen 3.8-27b.


## code style

single tab indent, only necessary comments

do not use react, no typescript

