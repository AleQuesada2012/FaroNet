//! Starter HTTP handler. Public application features remain to be implemented.

use worker::{event, Context, Env, Method, Request, Response, Result};

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
