/**
 * Frontend Component Test Specification for Source Provenance and Panel.
 *
 * Note: The repository frontend does not currently include a test runner in package.json
 * (only `typecheck`, `lint`, and `build`). This specification encodes the exact verification
 * assertions for matched button focusability, untraced styling, and panel origin rendering.
 */

import React from "react"
import { ChatPane, type ChatMessage } from "../components/chat-pane"
import { SourcePanel } from "../components/source-panel"

export const TEST_PROVENANCE_CASES = {
  matchedNumberIsFocusableButton: {
    description: "Matched numbers render as focusable <button> elements with aria-label",
    message: {
      id: "a-1",
      role: "assistant",
      text: "Total revenue was $450,000 for the period.",
      provenance: [
        {
          claim: "$450,000",
          status: "matched",
          source: "data",
          query_id: 1,
          dataset: "Superstore",
          column: "sales",
          row_index: 0,
        },
      ],
    } as ChatMessage,
    expectedSelector: 'button[aria-label="Source of $450,000"]',
    expectedStyle: "underline decoration-dotted decoration-muted-foreground",
  },

  untracedNumberIsNotButton: {
    description: "Untraced numbers render as <span> elements with warn underline, not <button>",
    message: {
      id: "a-2",
      role: "assistant",
      text: "Total sales were $999,999 according to estimates.",
      untraced: ["$999,999"],
      provenance: [
        {
          claim: "$999,999",
          status: "untraced",
          source: "none",
        },
      ],
    } as ChatMessage,
    expectedSelector: 'span[title*="Untraced figure"]',
    forbiddenSelector: 'button[aria-label="Source of $999,999"]',
  },

  oldRunsShowNoClickableNumbers: {
    description: "Rehydrated legacy runs without provenance show plain text, no buttons or errors",
    message: {
      id: "a-3",
      role: "assistant",
      text: "Total sales was 1234 units.",
      provenance: undefined,
    } as ChatMessage,
    forbiddenSelector: "button[aria-label*='Source of']",
  },

  panelRendersOrigins: {
    canonicalLabels: [
      "From your data",
      "Calculated by Python",
      "Stated in your message",
      "Not found in the data",
      "Dataset removed",
      "Based on a partial result",
    ],
    canonicalNotice: "Calculated numbers trace to a query or a calculation, not a single sheet cell.",
  },
}

