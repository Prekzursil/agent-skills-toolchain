Retiring a workflow by deleting its entry breaks every pinned consumer. Silent removal is the failure mode; the rollback class exists precisely because someone shipped a hard break. Do not do this.
