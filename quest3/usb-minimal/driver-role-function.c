// SPDX-License-Identifier: GPL-2.0-only
/* Unmodified test fixture from dwc3-msm-core.c, kernel dbc2bc83a2b6. */
static int dwc3_msm_check_extcon_prop(struct platform_device *pdev)
{
	struct dwc3_msm	*mdwc = platform_get_drvdata(pdev);
	struct device_node *node = mdwc->dev->of_node;
	int ret = 0;

	/* Check charger detection type to obtain charger type */
	if (of_get_property(node, "io-channel-names", NULL))
		mdwc->apsd_source = IIO;
	else if (of_get_property(node, "usb-role-switch", NULL))
		mdwc->apsd_source = REMOTE_PROC;
	else
		mdwc->apsd_source = PSY;

	if (of_property_read_bool(node, "extcon")) {
		ret = dwc3_msm_extcon_register(mdwc);
		if (ret)
			return ret;

		/*
		 * dpdm regulator will be turned on to perform apsd
		 * (automatic power source detection). dpdm regulator is
		 * used to float (or high-z) dp/dm lines. Do not reset
		 * controller/phy if regulator is turned on.
		 * if dpdm is not present controller can be reset
		 * as this controller may not be used for charger detection.
		 */
		mdwc->dpdm_reg = devm_regulator_get_optional(&pdev->dev,
				"dpdm");
		if (IS_ERR(mdwc->dpdm_reg)) {
			dev_dbg(mdwc->dev, "assume cable is not connected\n");
			mdwc->dpdm_reg = NULL;
		}

		if (!mdwc->vbus_active && mdwc->dpdm_reg &&
				regulator_is_enabled(mdwc->dpdm_reg)) {
			mdwc->dpdm_nb.notifier_call = dwc_dpdm_cb;
			regulator_register_notifier(mdwc->dpdm_reg,
					&mdwc->dpdm_nb);
		} else {
			if (!mdwc->role_switch)
				queue_delayed_work(mdwc->sm_usb_wq,
							&mdwc->sm_work, 0);
		}
	}

	if (!mdwc->role_switch && !mdwc->extcon) {
		switch (mdwc->dr_mode) {
		case USB_DR_MODE_OTG:
			if (of_property_read_bool(node,
						"qcom,default-mode-host")) {
				dev_dbg(mdwc->dev, "%s: start host mode\n",
								__func__);
				mdwc->id_state = DWC3_ID_GROUND;
			} else if (of_property_read_bool(node,
						"qcom,default-mode-none")) {
				dev_dbg(mdwc->dev, "%s: stay in none mode\n",
								__func__);
			} else {
				dev_dbg(mdwc->dev, "%s: start peripheral mode\n",
								__func__);
				mdwc->vbus_active = true;
			}
			break;
		case USB_DR_MODE_HOST:
			mdwc->id_state = DWC3_ID_GROUND;
			break;
		case USB_DR_MODE_PERIPHERAL:
			fallthrough;
		default:
			mdwc->vbus_active = true;
			break;
		}

		dwc3_ext_event_notify(mdwc);
	}

	return ret;
}

