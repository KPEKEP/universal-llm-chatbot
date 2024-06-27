#!/usr/bin/env bash

ollama serve &
ollama pull llama3:8b
ollama pull aya:latest
ollama pull deepseek-coder-v2:16b-lite-instruct-q8_0