---
name: openai-inference
description: Use this to write code to call OpenAI models using LiteLLM
---

# Calling OpenAI Models

These instructions allow you to write code to call OpenAI models using LiteLLM.

## Setup

The OPENAI_API_KEY must be set in the .env file and loaded as an environment variable.

The uv project must include litellm and pydantic.

    uv add litellm pydantic

## Code snippets

Use code like these examples to call OpenAI models.

### Imports and constants

    from litellm import completion

    MODEL = "gpt-4.1-mini"

### Code to call OpenAI for a text response

    response = completion(
        model=MODEL,
        messages=messages
    )

    result = response.choices[0].message.content

### Code to call OpenAI for a Structured Outputs response

    response = completion(
        model=MODEL,
        messages=messages,
        response_format=MyBaseModelSubclass
    )

    result = response.choices[0].message.content
    result_as_object = MyBaseModelSubclass.model_validate_json(result)