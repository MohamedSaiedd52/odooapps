import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";
import { user } from "@web/core/user";
import { getReportUrl } from "@web/webclient/actions/reports/utils";

registry
    .category("ir.actions.report handlers")
    .add("xlsx_handler", async (action, options, env) => {
        if (action.report_type !== "xlsx") {
            return false;
        }
        const url = getReportUrl(action, "xlsx");
        env.services.ui.block();
        try {
            await download({
                url: "/report/download",
                data: {
                    data: JSON.stringify([url, action.report_type]),
                    context: JSON.stringify({
                        ...user.context,
                        ...action.context,
                    }),
                },
            });
        } finally {
            env.services.ui.unblock();
        }
        return true;
    });
