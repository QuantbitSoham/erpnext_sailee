# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate

from erpnext.stock.doctype.item.item import get_item_defaults


class BlanketOrder(Document):
	# @frappe.whitelist()    
	# def somsg(self):
	# 	invoice_items = frappe.get_all(	"Sales Invoice Item",filters={"cost_center": "Distribution - SEP"},	fields=["name", "parent", "cost_center"],)
	# 	invoices_to_update = []
	# 	for item in invoice_items:
	# 		invoices = frappe.get_all("Sales Invoice",filters={"name": item.parent, "is_opening": "Yes"},fields=["name"],)
	# 		invoices_to_update.extend(invoices)

	# 	for invoice in invoices_to_update:
	# 		frappe.msgprint(invoice.name)
	# 		frappe.msgprint(item.parent)
	# 		frappe.msgprint(item.cost_center)

	# 	invoice_names = [invoice.name for invoice in invoices_to_update]
	# 	frappe.db.set_value("Sales Invoice",{"name": ["in", invoice_names]},"cost_center",	"Distribution - SEP",)
					
						
	# @frappe.whitelist()  
	# def somsg(self):
	# 	doc=frappe.get_all("Purchase Invoice",fields =["name","bill_no","bill_date","tid","tdate"])
	# 	for d in doc:
	# 		if not d.tdate :	
	# 			moc=frappe.get_all("Purchase Invoice Item",filters = {"parent": d.name} ,fields = ["purchase_receipt","name"], limit =1)
	# 			for m in moc:
	# 				if m.purchase_receipt:
	# 					prdoc=frappe.get_all("Purchase Receipt",filters ={"name":m.purchase_receipt}, fields =["bill_no","bill_date","name"],limit=1)
	# 					for o in prdoc:
	# 						frappe.msgprint("kkkkll")
	# 						frappe.set_value("Purchase Invoice",d.name ,"tid", o.bill_no)
	# 						frappe.set_value("Purchase Invoice",d.name,"tdate",o.bill_date)

	

	def validate(self):
		self.validate_dates()
		self.validate_duplicate_items()

	def validate_dates(self):
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From date cannot be greater than To date"))

	def validate_duplicate_items(self):
		item_list = []
		for item in self.items:
			if item.item_code in item_list:
				frappe.throw(_("Note: Item {0} added multiple times").format(frappe.bold(item.item_code)))
			item_list.append(item.item_code)

	def update_ordered_qty(self):
		ref_doctype = "Sales Order" if self.blanket_order_type == "Selling" else "Purchase Order"
		item_ordered_qty = frappe._dict(
			frappe.db.sql(
				"""
			select trans_item.item_code, sum(trans_item.stock_qty) as qty
			from `tab{0} Item` trans_item, `tab{0}` trans
			where trans.name = trans_item.parent
				and trans_item.blanket_order=%s
				and trans.docstatus=1
				and trans.status not in ('Closed', 'Stopped')
			group by trans_item.item_code
		""".format(
					ref_doctype
				),
				self.name,
			)
		)

		for d in self.items:
			d.db_set("ordered_qty", item_ordered_qty.get(d.item_code, 0))


@frappe.whitelist()
def make_order(source_name):
	doctype = frappe.flags.args.doctype

	def update_doc(source_doc, target_doc, source_parent):
		if doctype == "Quotation":
			target_doc.quotation_to = "Customer"
			target_doc.party_name = source_doc.customer

	def update_item(source, target, source_parent):
		target_qty = source.get("qty") - source.get("ordered_qty")
		target.qty = target_qty if not flt(target_qty) < 0 else 0
		item = get_item_defaults(target.item_code, source_parent.company)
		if item:
			target.item_name = item.get("item_name")
			target.description = item.get("description")
			target.uom = item.get("stock_uom")
			target.against_blanket_order = 1
			target.blanket_order = source_name

	target_doc = get_mapped_doc(
		"Blanket Order",
		source_name,
		{
			"Blanket Order": {"doctype": doctype, "postprocess": update_doc},
			"Blanket Order Item": {
				"doctype": doctype + " Item",
				"field_map": {"rate": "blanket_order_rate", "parent": "blanket_order"},
				"postprocess": update_item,
			},
		},
	)
	return target_doc
