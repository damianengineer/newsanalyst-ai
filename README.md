# News Analyst

> **⚠️ EDUCATIONAL USE ONLY**: This software is intended for educational and research purposes only. It should not be used in production environments without additional security testing and professional code review.

<details>
<summary><strong>Security Policy</strong></summary>

### Security Features
- Secure API key management via environment variables and 1Password integration
- Sensitive data redaction in logs
- Input validation and sanitization
- Configurable timeouts for external API calls

### Reporting Security Issues
If you discover a security vulnerability, privacy concern, or bug, please report it to:

```
fixit [dot] github [at] attentiontransformer [dot] com
```

Issues will be addressed on a best-effort basis. We appreciate your help in making this project more secure.
</details>

<details>
<summary><strong>How to Contribute</strong></summary>

We welcome contributions to improve News Analyst! To get involved:

> **📣 JOURNALISTS & MEDIA EXPERTS NEEDED!** We're actively seeking input from journalists, media scholars, and fact-checking professionals to enhance our evaluation framework with:
> - Reputable references for journalistic best practices
> - Examples of excellent journalism that demonstrate these principles
> - Examples of poor journalism and common shortcomings
> - Case studies of disinformation and manipulation techniques
> 
> Your expertise is invaluable in improving the quality and accuracy of our analysis.

1. Email us at:
   ```
   collaborate [dot] github [at] attentiontransformer [dot] com
   ```

2. Include in your email:
   - Your GitHub username
   - Areas you're interested in contributing to
   - Any relevant experience or skills
   - For journalists/media experts: examples or resources you can provide

3. Once approved, you'll receive access to contribute directly to the repository.

We're particularly interested in contributions related to:
- Improving extraction reliability
- Enhancing analysis quality
- Adding new features from the Future Work section
- Fixing bugs and addressing security concerns
- Improving documentation
- Expanding our journalistic evaluation criteria and reference materials
</details>

<details>
<summary><strong>License</strong></summary>

MIT License

Copyright (c) 2025 News Analyst Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
</details>

<details>
<summary><strong>Overview</strong></summary>

A modular workflow for analyzing news articles using Claude 3.7.

News Analyst is a Python application that extracts content from news articles and uses Claude 3.7 to analyze them for credibility, bias, and factual accuracy. It employs a three-step prompt flow to provide comprehensive analysis of news content.
</details>

## Example Analysis

News Analyst provides detailed evaluations of articles based on journalistic principles. Here are two example outputs:

<table>
<tr>
<th>Poor Journalism/Disinformation Example</th>
<th>High-Quality Journalism Example</th>
</tr>
<tr>
<td>

### "100 Days of Hoaxes: Cutting Through the Fake News"

**Reliability Score: 3 points**  
**Assessment Category: Unreliable**

| Assessment Area | Rating | Critical Concerns |
|-----------------|:------:|-------------------|
| Source Architecture | 🔴 | No external sources cited |
| Evidence Quality | 🔴 | Claims presented without evidence |
| Logical Framework | 🔴 | Circular reasoning, confirmation bias |
| Verification Transparency | 🔴 | No verification methods disclosed |
| Narrative Construction | 🔴 | Emotionally manipulative language |

**Critical Issues:**
- Presents opinion as fact
- Lacks independent verification
- Uses misleading framing techniques
- Contains factual inaccuracies
- Relies on anonymous sources

</td>
<td>

### "Hannah Dreier Wins Pulitzer Prize for Investigative Reporting"

**Reliability Score: 4 points**  
**Assessment Category: Exercise Caution**

| Assessment Area | Rating | Critical Concerns |
|-----------------|:------:|-------------------|
| Source Architecture | 🟡 | Heavy reliance on single perspective |
| Evidence Quality | 🟡 | Vague substantiation of impact claims |
| Logical Framework | 🟢 | Generally sound for achievement piece |
| Verification Transparency | 🟡 | Limited insight into reporting methodology |
| Narrative Construction | 🟡 | Celebratory framing prioritizes triumph |

**Strengths:**
- Accurately reports verifiable award information
- Provides context on the significance of the reporting
- Includes relevant background information
- Maintains professional tone
- Cites authoritative sources

</td>
</tr>
</table>

Each analysis includes a detailed breakdown of the article's strengths and weaknesses, allowing readers to make more informed judgments about the content's reliability.

<details>
<summary><strong>Motivation and Intended Use</strong></summary>

News Analyst was created to explore how Large Language Models (LLMs) can augment human consumption of news content. By applying objective reasoning about journalistic principles and analyzing the contents of articles, the tool helps readers:

- Identify potential biases and factual inaccuracies
- Understand the quality of sources and evidence used
- Recognize narrative techniques that may influence perception
- Make more informed decisions about the reliability of news content

The application uses a deterministic workflow to retrieve content from articles and analyze them consistently, providing structured output that highlights critical aspects of journalistic quality. The analysis is based on a comprehensive [evaluation framework](evaluation_framework.md) that establishes clear criteria for assessing news content across multiple dimensions.

News Analyst is intended for educational and research purposes, helping users develop critical media literacy skills in an increasingly complex information landscape.
</details>

<details>
<summary><strong>Features</strong></summary>

- **Multi-Strategy Content Extraction**: Employs multiple robust methods (trafilatura, newspaper3k, Selenium) to retrieve article content even from sites with anti-scraping measures
- **Three-Step Analysis Workflow**: Initial analysis → introspection → structured output format for consistent, high-quality results
- **Paywall Detection**: Identifies paywalled content and warns about limited extraction
- **Secure API Key Management**: Retrieves secrets from 1Password vault and environment variables
- **Structured Logging**: JSON-compatible logs with automatic sensitive data redaction
- **Advanced Browser Emulation**: Handles sophisticated anti-scraping measures with configurable browser fingerprinting
- **Token Usage Tracking**: Monitors and reports Claude API token consumption for cost management
- **Hyperlink Analysis**: Extracts and filters relevant hyperlinks from articles for reference analysis
- **Configurable Timeout Handling**: Manages API request timeouts for complex articles
- **Static Type Checking**: Improves code quality and catches errors with mypy integration
- **Centralized Configuration**: YAML-based configuration for all application settings
- **Formatted Output**: Generates both human-readable Markdown and machine-readable JSON results
</details>

<details>
<summary><strong>Installation</strong></summary>

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/newsanalyst.git
   cd newsanalyst
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Claude API key:
   - Option 1: Set the `ANTHROPIC_API_KEY` environment variable
   - Option 2: Configure 1Password integration in `config.yaml`
</details>

## Quickstart

Follow these steps to quickly get started with News Analyst:

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/newsanalyst.git
   cd newsanalyst
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get a Claude API key**
   - Sign up at [Anthropic's website](https://www.anthropic.com/)
   - Create an API key in your account dashboard

4. **Set up your API key** (choose one method)
   - **RECOMMENDED:** 1Password integration (most secure)
     ```yaml
     # In config.yaml
     api:
       claude:
         onepassword:
           enabled: true
           vault: "Private"
           item: "Anthropic API Key"
           field: "api_key"
     ```
   - Environment variable (less secure):
     ```bash
     # macOS/Linux
     export ANTHROPIC_API_KEY=your_api_key_here
     
     # Windows
     set ANTHROPIC_API_KEY=your_api_key_here
     ```

5. **Add URLs to analyze**
   - Edit `url_input.txt` in the root directory
   - Add one URL per line

6. **Run the analyzer**
   ```bash
   python newsanalyst.py
   ```

7. **View results**
   - Check the `output` directory for Markdown and JSON analysis files

That's it! For more advanced usage and configuration options, see the sections below.

<details>
<summary><strong>Command-Line Options</strong></summary>

```
usage: newsanalyst.py [-h] [-u URL | -f FILE] [--config CONFIG] [--output-dir OUTPUT_DIR]
```

### Basic Options

| Flag | Long Form | Description | Default |
|------|-----------|-------------|---------|
| `-h` | `--help` | Show help message and exit | |
| `-u URL` | `--url URL` | URL of the news article to analyze | |
| `-f FILE` | `--file FILE` | File containing URLs to analyze (one per line) | |

### Configuration Options

| Flag | Long Form | Description | Default |
|------|-----------|-------------|---------|
| | `--config CONFIG` | Path to configuration file | `config.yaml` |
| `-o DIR` | `--output-dir DIR` | Output directory (overrides config) | Value from config file |

### Examples

Analyze a single URL:
```bash
python newsanalyst.py -u https://www.example.com/article
```

Analyze multiple URLs from a file:
```bash
python newsanalyst.py -f my_urls.txt
```

Use a custom configuration file:
```bash
python newsanalyst.py --config custom_config.yaml
```

Specify a custom output directory:
```bash
python newsanalyst.py -o ./my_analyses
```

Use default URL input file with custom output directory:
```bash
python newsanalyst.py --output-dir ./my_analyses
```
</details>

<details>
<summary><strong>Configuration</strong></summary>

News Analyst uses a YAML configuration file (`config.yaml`) for all settings. The default configuration looks like this:

```yaml
api:
  claude:
    api_key: ""
    env_var_name: "ANTHROPIC_API_KEY"
    onepassword:
      enabled: false
      vault: "Private"
      item: "Anthropic API Key"
      field: "api_key"
model:
  name: "claude-3-7-sonnet-20250219"
  temperature: 0.3
  max_tokens: 4096
prompts:
  system_prompt: "prompts/system_prompt.txt"
  initial_prompt: "prompts/initial_prompt.txt"
  introspection_prompt: "prompts/introspection_prompt.txt"
  output_format_prompt: "prompts/output_format.txt"
output:
  directory: "output"
logging:
  level: "INFO"
  file: "newsanalyst.log"
```

You can override these settings by:
1. Editing the `config.yaml` file directly
2. Providing a custom configuration file with the `--config` parameter
3. Using command-line arguments to override specific settings
</details>

<details>
<summary><strong>Usage</strong></summary>

### Analyze a single URL

```
python newsanalyst.py -u https://example.com/news/article
```

### Analyze multiple URLs from a file

```
python newsanalyst.py -f urls.txt
```

### Use a custom configuration file

```
python newsanalyst.py -u https://example.com/news/article --config my_config.yaml
```

### Override specific settings

```
python newsanalyst.py -u https://example.com/news/article --api-key YOUR_API_KEY --output-dir custom_output
```
</details>

<details>
<summary><strong>Output</strong></summary>

For each analyzed article, News Analyst generates:
- A Markdown file with the formatted analysis
- A JSON file with structured data about the article and analysis
</details>

<details>
<summary><strong>Customizing Prompts</strong></summary>

You can customize the analysis by editing the prompt files in the `prompts/` directory:
- `system_prompt.txt`: Sets the context for Claude
- `initial_prompt.txt`: Instructions for the initial analysis
- `introspection_prompt.txt`: Instructions for the introspection step
- `output_format.txt`: Instructions for formatting the final output
</details>

<details>
<summary><strong>Authentication Options</strong></summary>

News Analyst supports three methods for Claude API authentication:

1. **Direct API Key**:
   - Set `api.claude.api_key` in `config.yaml`
   - Least secure, not recommended for production

2. **Environment Variable**:
   - Set the `ANTHROPIC_API_KEY` environment variable
   - Default fallback method

3. **1Password Integration**:
   - Enable with `api.claude.onepassword.enabled: true` in `config.yaml`
   - Configure vault, item, and field names
   - Most secure option for production use
</details>

<details>
<summary><strong>Development Tools</strong></summary>

### Structured Logging

News Analyst uses `structlog` for enhanced logging capabilities:

```python
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Basic logging
logger.info("Processing article", url=article_url)

# Contextual logging
logger.error("API request failed", 
             status_code=response.status_code, 
             error=response.text,
             retry_count=retry_count)
```

Structured logs include timestamps, log levels, and contextual information in a consistent format.

### Type Checking

Run static type checking with mypy:

```
./check_types.py
```

This will analyze the codebase for type errors and provide suggestions for improvement.
</details>

<details>
<summary><strong>Future Work</strong></summary>

The following improvements are planned for future releases:

1. **Anthropic API Integration**
   - Replace custom REST API client with the official `anthropic` Python SDK
   - Benefits: Better error handling, automatic retries, streaming support

2. **Web Scraping Modernization**
   - Replace Selenium WebDriver with Playwright
   - Benefits: Better performance, easier headless mode, modern browser support

3. **Asynchronous Processing**
   - Implement async with `asyncio`, `httpx`, and `aiofiles`
   - Benefits: Parallel processing of multiple articles, improved throughput

4. **Content Extraction Enhancement**
   - Replace newspaper3k with `readability-lxml` or `goose3`
   - Benefits: Better extraction quality, maintained libraries

5. **Image Extraction and Processing**
   - Add support for extracting and analyzing images from articles
   - Implement image metadata extraction and content analysis
   - Benefits: More comprehensive analysis including visual elements

6. **Web Browsing Capabilities**
   - Integrate MPC (Multi-Party Computation) tools for secure web browsing
   - Allow Claude API to browse the web via Cloudflare Workers
   - Benefits: Real-time fact-checking and reference verification

7. **Extended Thinking Mode**
   - Add configuration parameter for Claude's extended thinking capabilities
   - Implement streaming interaction for real-time response generation
   - Benefits: More thorough analysis for complex articles

8. **Enhanced Evaluation Framework**
   - Expand evaluation_framework.md with features enabled by the above enhancements
   - Create metrics for measuring analysis quality and accuracy
   - Benefits: Better assessment of system performance

9. **Continuous Optimization**
   - Improve accuracy through better prompt engineering and model selection
   - Enhance error handling with more robust fallback mechanisms
   - Optimize performance with caching and resource management
   - Strengthen security practices for API key and content handling
   - Refactor codebase following Pythonic best practices

10. **Comprehensive Test Suite**
    - Implement complete unit testing for all modules
    - Add integration tests for end-to-end workflows
    - Create mock objects for external dependencies
    - Implement test coverage reporting
    - Add automated regression testing
    - Develop benchmark tests for performance monitoring
    - Benefits: Improved reliability, easier maintenance, and safer refactoring
</details>
