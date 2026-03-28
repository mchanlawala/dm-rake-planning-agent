# Rake Planning Optimization System

## Overview
An intelligent system for optimizing steel coil loading into railway rakes, using AI-powered insights and configurable business rules.

## Features
- **Excel-based Configuration**: All constraints read from Excel input files
- **Intelligent Optimization**: Greedy algorithm with combination validation
- **Multiple Rake Types**: Support for Concord and Jumbo rakes
- **Width Category Management**: NARROW, WIDER, EXTRA categories with custom ranges
- **Valid Combination Validation**: Enforces business rules for wagon loading
- **LLM Integration**: Optional insights from Ollama (local) or OpenAI (cloud)
- **Comprehensive Output**: Detailed Excel reports with metrics and summaries

## Installation

### 1. Clone or download the project
```bash
cd rake-planning-agent