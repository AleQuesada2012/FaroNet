"""Future gateway implementation bridging FaroNet with the Rust edge Worker.

Only explicitly public messages may be relayed to public application routes.
Authentication, replay prevention, and HTTPS/WSS are pending design decisions.
"""
