//! Offline authentication foundation and the existing Worker health handler.

pub mod gateway_auth;

#[cfg(target_arch = "wasm32")]
use worker::{event, Context, Env, Method, Request, Response, Result};

#[cfg(target_arch = "wasm32")]
#[event(fetch)]
async fn fetch(request: Request, _env: Env, _context: Context) -> Result<Response> {
    match (request.method(), request.path().as_str()) {
        (Method::Get, "/health") => Response::ok("FaroNet edge scaffold ready"),
        (Method::Get, "/") => Response::ok(
            "FaroNet Rust edge scaffold. See /health. Application features are pending.",
        ),
        _ => Response::error("Not found", 404),
    }
}
