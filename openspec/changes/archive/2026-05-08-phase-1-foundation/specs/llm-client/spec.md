## ADDED Requirements

### Requirement: Provider-abstracted LLM client interface
The system SHALL define an `LLMClient` interface (Python `Protocol` or abstract base) exposing a single `complete(messages, *, model=None)` method that returns a response object carrying the assistant's text content and token usage (prompt, completion, total).

#### Scenario: Successful completion
- **WHEN** a caller invokes `client.complete(messages=[...])`
- **THEN** the returned object exposes a non-empty `content: str` and a `usage` object with non-negative integer `prompt`, `completion`, and `total` token counts

#### Scenario: Multiple implementations possible
- **WHEN** a new provider implementation is added in a future phase
- **THEN** it MUST satisfy the same `LLMClient` interface without changes to its callers

### Requirement: Moonshot is the only implementation
The system SHALL ship exactly one `LLMClient` implementation, targeting Moonshot (Kimi). The implementation MUST authenticate using the `MOONSHOT_API_KEY` environment variable and MUST send requests to `https://api.moonshot.ai/v1` (Moonshot's OpenAI-compatible endpoint).

#### Scenario: Authentication
- **WHEN** the Moonshot client is instantiated and `MOONSHOT_API_KEY` is set
- **THEN** subsequent `complete` calls include the API key in the `Authorization` header

#### Scenario: Missing API key
- **WHEN** `MOONSHOT_API_KEY` is unset and the Moonshot client is instantiated
- **THEN** instantiation (or the first `complete` call) raises a clear error naming the missing variable

#### Scenario: No other providers
- **WHEN** the codebase is inspected
- **THEN** no client targeting Anthropic, OpenAI, or any other provider exists

### Requirement: Flagship Kimi model by default
The Moonshot client SHALL default to a flagship Kimi coding-tier model for `complete` calls and SHALL allow the model to be overridden per call or via configuration (`--model` flag or `MOONSHOT_MODEL` env var).

#### Scenario: Default model
- **WHEN** `complete` is called without an explicit `model` argument and no override is configured
- **THEN** the request uses the configured flagship Kimi model name

#### Scenario: Override via env var
- **WHEN** `MOONSHOT_MODEL` is set in the environment
- **THEN** that value is used as the default model for `complete` calls

### Requirement: Token-usage reporting
The Moonshot client SHALL surface token usage from each completion in Moonshot tokens, parsed from the provider response.

#### Scenario: Usage parsed from response
- **WHEN** Moonshot returns a successful completion with a `usage` field
- **THEN** the returned response object exposes prompt, completion, and total token counts matching that field
