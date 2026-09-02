/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/
/* eslint-disable local/code-no-unexternalized-strings */

//#region proposals
/**
 * MCP protocol proposals.
 * - Proposals here MUST have an MCP PR linked to them
 * - Proposals here are subject to change and SHALL be removed when
 *   the upstream MCP PR is merged or closed.
 */
export namespace MCP {

	// Nothing, yet

}

//#endregion

/**
 * Schema updated from the Model Context Protocol repository at
 * https://github.com/modelcontextprotocol/specification/tree/main/schema
 *
 * ⚠️ Do not edit within `namespace` manually except to update schema versions ⚠️
 */
export namespace MCP {
	/* JSON-RPC types */

	/**
	 * Refers to any valid JSON-RPC object that can be decoded off the wire, or encoded to be sent.
	 *
	 * @category JSON-RPC
	 */
	export type JSONRPCMessage =
		| JSONRPCRequest
		| JSONRPCNotification
		| JSONRPCResponse
		| JSONRPCError;

	/** @internal */
	export const LATEST_PROTOCOL_VERSION = "2025-11-25";
	/** @internal */
	export const JSONRPC_VERSION = "2.0";

	/**
	 * A progress token, used to associate progress notifications with the original request.
	 *
	 * @category Common Types
	 */
	export type ProgressToken = string | number;

	/**
	 * An opaque token used to represent a cursor for pagination.
	 *
	 * @category Common Types
	 */
	export type Cursor = string;

	/**
	 * Common params for any task-augmented request.
	 *
	 * @internal
	 */
	export interface TaskAugmentedRequestParams extends RequestParams {
		/**
		 * If specified, the caller is requesting task-augmented execution for this request.
		 * The request will return a CreateTaskResult immediately, and the actual result can be
		 * retrieved later via tasks/result.
		 *
		 * Task augmentation is subject to capability negotiation - receivers MUST declare support
		 * for task augmentation of specific request types in their capabilities.
		 */
		task?: TaskMetadata;
	}
	/**
	 * Common params for any request.
	 *
	 * @internal

/* --- ClientCapabilities/ServerCapabilities excerpt --- */
export interface ClientCapabilities {
		/**
		 * Experimental, non-standard capabilities that the client supports.
		 */
		experimental?: { [key: string]: object };
		/**
		 * Present if the client supports listing roots.
		 */
		roots?: {
			/**
			 * Whether the client supports notifications for changes to the roots list.
			 */
			listChanged?: boolean;
		};
		/**
		 * Present if the client supports sampling from an LLM.
		 */
		sampling?: {
			/**
			 * Whether the client supports context inclusion via includeContext parameter.
			 * If not declared, servers SHOULD only use `includeContext: "none"` (or omit it).
			 */
			context?: object;
			/**
			 * Whether the client supports tool use via tools and toolChoice parameters.
			 */
			tools?: object;
		};
		/**
		 * Present if the client supports elicitation from the server.
		 */
		elicitation?: { form?: object; url?: object };

		/**
		 * Present if the client supports task-augmented requests.
		 */
		tasks?: {
			/**
			 * Whether this client supports tasks/list.
			 */
			list?: object;
			/**
			 * Whether this client supports tasks/cancel.
			 */
			cancel?: object;
			/**
			 * Specifies which request types can be augmented with tasks.
			 */
			requests?: {
				/**
				 * Task support for sampling-related requests.
				 */
				sampling?: {
					/**
					 * Whether the client supports task-augmented sampling/createMessage requests.
					 */
					createMessage?: object;
				};
				/**
				 * Task support for elicitation-related requests.
				 */
				elicitation?: {
					/**
					 * Whether the client supports task-augmented elicitation/create requests.
					 */
					create?: object;
				};
			};
		};
	}

	/**
	 * Capabilities that a server may support. Known capabilities are defined here, in this schema, but this is not a closed set: any server can define its own, additional capabilities.
	 *
	 * @category `initialize`
	 */
	export interface ServerCapabilities {
		/**
		 * Experimental, non-standard capabilities that the server supports.
		 */
		experimental?: { [key: string]: object };
		/**
		 * Present if the server supports sending log messages to the client.
		 */
		logging?: object;
		/**
		 * Present if the server supports argument autocompletion suggestions.
		 */
		completions?: object;
		/**
		 * Present if the server offers any prompt templates.
		 */
		prompts?: {
			/**
			 * Whether this server supports notifications for changes to the prompt list.
			 */
			listChanged?: boolean;
		};
		/**
		 * Present if the server offers any resources to read.
		 */
		resources?: {
			/**
			 * Whether this server supports subscribing to resource updates.
			 */
			subscribe?: boolean;
			/**
			 * Whether this server supports notifications for changes to the resource list.
			 */
			listChanged?: boolean;
		};
		/**
		 * Present if the server offers any tools to call.
		 */
		tools?: {
			/**
			 * Whether this server supports notifications for changes to the tool list.
			 */
			listChanged?: boolean;
		};
		/**
		 * Present if the server supports task-augmented requests.
		 */
		tasks?: {
			/**
			 * Whether this server supports tasks/list.
			 */
			list?: object;
			/**
			 * Whether this server supports tasks/cancel.
			 */
			cancel?: object;
			/**
			 * Specifies which request types can be augmented with tasks.
			 */
			requests?: {
				/**
				 * Task support for tool-related requests.
				 */
				tools?: {
					/**
					 * Whether the server supports task-augmented tools/call requests.
					 */
					call?: object;
				};
			};
		};
	}

	/**
	 * An optionally-sized icon that can be displayed in a user interface.
	 *
	 * @category Common Types
	 */
	export interface Icon {
		/**
		 * A standard URI pointing to an icon resource. May be an HTTP/HTTPS URL or a
		 * `data:` URI with Base64-encoded image data.
		 *
		 * Consumers SHOULD takes steps to ensure URLs serving icons are from the
		 * same domain as the client/server or a trusted domain.
		 *
		 * Consumers SHOULD take appropriate precautions when consuming SVGs as they can contain
		 * executable JavaScript.
		 *
		 * @format uri
		 */
		src: string;

		/**
		 * Optional MIME type override if the source MIME type is missing or generic.
		 * For example: `"image/png"`, `"image/jpeg"`, or `"image/svg+xml"`.
		 */
		mimeType?: string;

		/**
		 * Optional array of strings that specify sizes at which the icon can be used.
		 * Each string should be in WxH format (e.g., `"48x48"`, `"96x96"`) or `"any"` for scalable formats like SVG.
		 *
		 * If not provided, the client should assume that the icon can be used at any size.
		 */
		sizes?: string[];

		/**
		 * Optional specifier for the theme this icon is designed for. `light` indicates
		 * the icon is designed to be used with a light background, and `dark` indicates
		 * the icon is designed to be used with a dark background.
		 *
		 * If not provided, the client should assume the icon can be used with any theme.
		 */
		theme?: "light" | "dark";
	}

	/**
	 * Base interface to add `icons` property.
	 *
	 * @internal
	 */
	export interface Icons {
		/**
		 * Optional set of sized icons that the client can display in a user interface.
		 *
		 * Clients that support rendering icons MUST support at least the following MIME types:
		 * - `image/png` - PNG images (safe, universal compatibility)
		 * - `image/jpeg` (and `image/jpg`) - JPEG images (safe, universal compatibility)
		 *
		 * Clients that support rendering icons SHOULD also support:
		 * - `image/svg+xml` - SVG images (scalable but requires security precautions)
		 * - `image/webp` - WebP images (modern, efficient format)
		 */
		icons?: Icon[];
	}

	/**
	 * Base interface for metadata with name (identifier) and title (display name) properties.
	 *
	 * @internal
	 */
	export interface BaseMetadata {
		/**
		 * Intended for programmatic or logical use, but used as a display name in past specs or fallback (if title isn't present).
		 */
		name: string;

		/**
		 * Intended for UI and end-user contexts - optimized to be human-readable and easily understood,
		 * even by those unfamiliar with domain-specific terminology.
		 *
		 * If not provided, the name should be used for display (except for Tool,
		 * where `annotations.title` should be given precedence over using `name`,
		 * if present).
		 */
		title?: string;
	}

	/**
	 * Describes the MCP implementation.
	 *
	 * @category `initialize`
	 */
	
