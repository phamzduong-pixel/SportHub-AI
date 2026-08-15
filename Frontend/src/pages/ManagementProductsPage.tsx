import { Plus, Search, ShoppingBag } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  Input,
  LoadingSkeleton,
  Modal,
  PageHeader,
  useToast,
} from "@/components/common";
import { apiRequest } from "@/services/apiClient";
import {
  adjustInventory,
  createProduct,
  deleteProduct,
  getProductCatalog,
  importProductCatalog,
  listProducts,
  setProductActive,
  updateProduct,
  type FacilityProduct,
  type ProductCatalogSuggestion,
  type ProductPayload,
  type ProductStatus,
  type ProductType,
} from "@/services/productService";

interface Facility {
  id: number;
  name: string;
  sports: string[];
}
type FormState = Omit<ProductPayload, "description" | "image_url"> & {
  description: string;
  stock_quantity: number;
  track_inventory: boolean;
};
const defaultSports = [
  "Bóng đá",
  "Cầu lông",
  "Pickleball",
  "Tennis",
  "Bóng rổ",
  "Bóng chuyền",
];
const blank: FormState = {
  facility_id: 0,
  name: "",
  product_type: "SELL",
  description: "",
  price: 0,
  unit: "sản phẩm",
  sports: [],
  status: "ACTIVE",
  stock_quantity: 0,
  track_inventory: true,
};
const typeLabel: Record<ProductType, string> = {
  SELL: "Sản phẩm bán",
  RENT: "Cho thuê",
  SERVICE: "Dịch vụ",
};
const statusLabel: Record<ProductStatus, string> = {
  ACTIVE: "Đang hoạt động",
  INACTIVE: "Đã tắt",
  ARCHIVED: "Đã lưu trữ",
};
const money = (value: number) => `${Number(value).toLocaleString("vi-VN")}đ`;

export function ManagementProductsPage() {
  const { toast } = useToast();
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [items, setItems] = useState<FacilityProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<FacilityProduct>();
  const [form, setForm] = useState<FormState>(blank);
  const [query, setQuery] = useState("");
  const [facilityFilter, setFacilityFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [confirm, setConfirm] = useState<{
    kind: "toggle" | "stockout" | "delete";
    product: FacilityProduct;
  }>();
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [catalogSport, setCatalogSport] = useState(defaultSports[0]);
  const [catalog, setCatalog] = useState<ProductCatalogSuggestion[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogSelected, setCatalogSelected] = useState<string[]>([]);
  const [catalogFacilityId, setCatalogFacilityId] = useState(0);
  const catalogFacility = facilities.find((item) => item.id === (catalogFacilityId || facilities[0]?.id));
  const catalogSports = Array.from(new Set([...(catalogFacility?.sports || []), "Dùng chung"]));

  const load = async () => {
    setLoading(true);
    try {
      const [venueData, productData] = await Promise.all([
        apiRequest<Facility[]>("/facilities"),
        listProducts(),
      ]);
      setFacilities(venueData);
      setItems(productData);
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không tải được dữ liệu.",
        "error",
      );
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);

  const sports = useMemo(
    () =>
      Array.from(
        new Set([
          ...defaultSports,
          ...facilities.flatMap((item) => item.sports || []),
        ]),
      ),
    [facilities],
  );
  const shown = items.filter(
    (item) =>
      (facilityFilter === "all" ||
        String(item.facility_id) === facilityFilter) &&
      (typeFilter === "all" || item.product_type === typeFilter) &&
      (statusFilter === "all" || item.status === statusFilter) &&
      (!query.trim() ||
        `${item.name} ${item.description || ""}`
          .toLocaleLowerCase("vi")
          .includes(query.trim().toLocaleLowerCase("vi"))),
  );
  const merge = (product: FacilityProduct) =>
    setItems((current) =>
      current.some((item) => item.id === product.id)
        ? current.map((item) => (item.id === product.id ? product : item))
        : [product, ...current],
    );
  const openCreate = () => {
    setEditing(undefined);
    setForm({
      ...blank,
      facility_id: facilities[0]?.id || 0,
      sports: facilities[0]?.sports || [],
    });
    setFormOpen(true);
  };
  const loadCatalog = async (sport = catalogSport) => {
    setCatalogSport(sport);
    setCatalogSelected([]);
    setCatalogLoading(true);
    try {
      setCatalog(await getProductCatalog(sport));
      setCatalogOpen(true);
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không tải được catalog gợi ý.", "error");
    } finally {
      setCatalogLoading(false);
    }
  };
  const importCatalog = async () => {
    const facilityId = catalogFacilityId || facilities[0]?.id;
    if (!facilityId || !catalogSelected.length)
      return toast("Vui lòng chọn cơ sở và ít nhất một mục catalog.", "error");
    setSaving(true);
    try {
      const imported = await importProductCatalog({
        facility_id: facilityId,
        sport: catalogSport,
        catalog_keys: catalogSelected,
      });
      imported.forEach(merge);
      setCatalogOpen(false);
      setCatalogSelected([]);
      setFacilityFilter(String(facilityId));
      toast(`Đã đưa ${imported.length} sản phẩm vào cơ sở. Hãy sửa giá, số lượng rồi bật hoạt động.`, "success");
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không thể thêm catalog vào cơ sở.", "error");
    } finally {
      setSaving(false);
    }
  };
  const openEdit = (item: FacilityProduct) => {
    setEditing(item);
    setForm({
      facility_id: item.facility_id,
      name: item.name,
      product_type: item.product_type,
      description: item.description || "",
      price: item.price,
      unit: item.unit,
      sports: item.sports,
      status: item.status,
      stock_quantity: item.stock_quantity,
      track_inventory: item.track_inventory,
    });
    setFormOpen(true);
  };
  const closeForm = () => {
    setFormOpen(false);
    setEditing(undefined);
    setForm(blank);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.sports.length)
      return toast("Vui lòng chọn ít nhất một môn thể thao.", "error");
    if (form.track_inventory && (!Number.isInteger(form.stock_quantity) || form.stock_quantity < 0))
      return toast("Số lượng phải là số nguyên không âm.", "error");
    if (editing && form.track_inventory && form.stock_quantity < editing.reserved_quantity)
      return toast(`Số lượng không thể thấp hơn ${editing.reserved_quantity} đang được giữ cho booking.`, "error");
    if (editing && !form.track_inventory && editing.reserved_quantity > 0)
      return toast("Không thể tắt quản lý số lượng khi sản phẩm đang được giữ cho booking.", "error");
    setSaving(true);
    try {
      const { stock_quantity, track_inventory, ...metadata } = form;
      const payload: ProductPayload = {
        ...metadata,
        description: form.description.trim() || null,
        image_url: null,
        ...(editing ? {} : { stock_quantity, track_inventory }),
      };
      let saved = editing
        ? await updateProduct(editing.id, payload)
        : await createProduct(payload);
      if (editing && (
        editing.stock_quantity !== stock_quantity ||
        editing.track_inventory !== track_inventory
      )) {
        saved = await adjustInventory(editing.id, {
          stock_quantity,
          track_inventory,
          note: "OWNER cập nhật số lượng từ màn hình chỉnh sửa",
        });
      }
      merge(saved);
      closeForm();
      toast(editing ? "Đã cập nhật sản phẩm." : "Đã thêm sản phẩm.", "success");
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể lưu sản phẩm.",
        "error",
      );
    } finally {
      setSaving(false);
    }
  };

  const confirmedAction = async () => {
    if (!confirm) return;
    setSaving(true);
    try {
      if (confirm.kind === "toggle") {
        const updated = await setProductActive(
          confirm.product.id,
          confirm.product.status !== "ACTIVE",
        );
        merge(updated);
        toast(
          updated.status === "ACTIVE" ? "Đã bật sản phẩm." : "Đã tắt sản phẩm.",
          "success",
        );
      } else if (confirm.kind === "stockout") {
        const updated = await adjustInventory(confirm.product.id, {
          stock_quantity: confirm.product.reserved_quantity,
          track_inventory: true,
          note: "OWNER đánh dấu hết hàng",
        });
        merge(updated);
        toast("Đã đánh dấu hết hàng.", "success");
      } else {
        const result = await deleteProduct(confirm.product.id);
        if (result.action === "deleted")
          setItems((current) =>
            current.filter((item) => item.id !== confirm.product.id),
          );
        else if (result.product) merge(result.product);
        toast(
          result.message,
          result.action === "archived" ? "info" : "success",
        );
      }
    } catch (error) {
      toast(
        error instanceof Error ? error.message : "Không thể cập nhật sản phẩm.",
        "error",
      );
    } finally {
      setSaving(false);
      setConfirm(undefined);
    }
  };
  return (
    <>
      <PageHeader
        title="Dịch vụ & sản phẩm"
        description="Quản lý sản phẩm bán, cho thuê và dịch vụ theo từng cơ sở; giữ nguyên lịch sử khi đã có trong booking."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={!facilities.length || catalogLoading} onClick={() => void loadCatalog(catalogFacility?.sports?.[0] || "Dùng chung")}>
              Chọn từ catalog
            </Button>
            <Button
              leftIcon={<Plus size={17} />}
              disabled={!facilities.length}
              onClick={openCreate}
            >
              Thêm mới
            </Button>
          </div>
        }
      />
      <section className="mb-5 grid gap-3 rounded-card border border-slate-200 bg-white p-4 sm:grid-cols-2 xl:grid-cols-4">
        <label className="relative sm:col-span-2 xl:col-span-1">
          <span className="sr-only">Tìm kiếm</span>
          <Search size={17} className="absolute left-3 top-3 text-slate-400" />
          <input
            className="field pl-10"
            placeholder="Tìm tên sản phẩm…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <Filter
          value={facilityFilter}
          onChange={setFacilityFilter}
          options={[
            ["all", "Tất cả cơ sở"],
            ...facilities.map((item) => [String(item.id), item.name]),
          ]}
        />
        <Filter
          value={typeFilter}
          onChange={setTypeFilter}
          options={[["all", "Tất cả loại"], ...Object.entries(typeLabel)]}
        />
        <Filter
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            ["all", "Tất cả trạng thái"],
            ...Object.entries(statusLabel),
          ]}
        />
      </section>
      {loading ? (
        <LoadingSkeleton lines={8} />
      ) : shown.length ? (
        <div className="overflow-x-auto rounded-card border border-slate-200 bg-white">
          <table className="w-full min-w-[1050px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Tên</th><th className="px-4 py-3">Môn</th><th className="px-4 py-3">Loại</th><th className="px-4 py-3">Giá</th><th className="px-4 py-3">Số lượng</th><th className="px-4 py-3">Trạng thái</th><th className="px-4 py-3">Hành động</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((item) => {
                const outOfStock = item.status === "ACTIVE" && item.track_inventory && item.available_quantity <= 0;
                return (
                  <tr key={item.id} className="border-t align-top">
                    <td className="px-4 py-3"><b className="block">{item.name}</b><small className="block text-slate-500">{item.facility_name}</small>{item.description && <small className="mt-1 block max-w-64 text-slate-500">{item.description}</small>}</td>
                    <td className="px-4 py-3">{item.sports.join(", ")}</td>
                    <td className="px-4 py-3">{typeLabel[item.product_type]}</td>
                    <td className="px-4 py-3 font-semibold text-brand-700">{money(item.price)} / {item.unit}</td>
                    <td className="px-4 py-3">{item.track_inventory ? <><b>{item.stock_quantity}</b><small className="block text-slate-500">Còn {item.available_quantity}</small></> : "Không giới hạn"}</td>
                    <td className="px-4 py-3"><Badge variant={item.status === "ARCHIVED" ? "warning" : item.status === "INACTIVE" || outOfStock ? "neutral" : "success"}>{item.status === "ARCHIVED" ? "Đã xóa" : item.status === "INACTIVE" ? "Đã khóa" : outOfStock ? "Hết hàng" : "Đang hoạt động"}</Badge></td>
                    <td className="px-4 py-3"><div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" disabled={item.status === "ARCHIVED"} onClick={() => openEdit(item)}>Sửa</Button>
                      <Button size="sm" variant="outline" disabled={item.status === "ARCHIVED"} onClick={() => setConfirm({ kind: "toggle", product: item })}>{item.status === "ACTIVE" ? "Khóa" : "Mở"}</Button>
                      <Button size="sm" variant="outline" disabled={item.status === "ARCHIVED" || !item.track_inventory || outOfStock} onClick={() => setConfirm({ kind: "stockout", product: item })}>Hết hàng</Button>
                      <Button size="sm" variant="danger" disabled={item.status === "ARCHIVED"} onClick={() => setConfirm({ kind: "delete", product: item })}>Xóa</Button>
                    </div></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          icon={<ShoppingBag />}
          title="Chưa có dịch vụ hoặc sản phẩm phù hợp"
          description={
            facilities.length
              ? "Thay đổi bộ lọc hoặc thêm sản phẩm đầu tiên cho cơ sở."
              : "Hãy tạo cơ sở trước khi thêm dịch vụ và sản phẩm."
          }
        />
      )}
      <Modal
        open={formOpen}
        onClose={closeForm}
        title={
          editing ? "Chỉnh sửa dịch vụ / sản phẩm" : "Thêm dịch vụ / sản phẩm"
        }
      >
        <form onSubmit={save} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Cơ sở
              <select
                className="field mt-1.5"
                value={form.facility_id}
                onChange={(event) => {
                  const id = Number(event.target.value);
                  const venue = facilities.find((item) => item.id === id);
                  setForm({
                    ...form,
                    facility_id: id,
                    sports: venue?.sports || form.sports,
                  });
                }}
              >
                {facilities.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Loại
              <select
                className="field mt-1.5"
                value={form.product_type}
                onChange={(event) => {
                  const productType = event.target.value as ProductType;
                  setForm({
                    ...form,
                    product_type: productType,
                    track_inventory: productType !== "SERVICE",
                  });
                }}
              >
                {Object.entries(typeLabel).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Input
            required
            label="Tên"
            maxLength={160}
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
          <label className="block text-sm font-medium">
            Mô tả
            <textarea
              className="field mt-1.5 min-h-24 resize-y"
              maxLength={500}
              value={form.description}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              required
              type="number"
              min="0"
              step="1000"
              label="Giá"
              value={form.price}
              onChange={(event) =>
                setForm({ ...form, price: Number(event.target.value) })
              }
            />
            <Input
              required
              label="Đơn vị"
              placeholder="chai, giờ, lượt…"
              value={form.unit}
              onChange={(event) =>
                setForm({ ...form, unit: event.target.value })
              }
            />
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <label className="flex items-center gap-2 text-sm font-semibold">
                <input
                  type="checkbox"
                  className="accent-brand-600"
                  checked={form.track_inventory}
                  onChange={(event) =>
                    setForm({ ...form, track_inventory: event.target.checked })
                  }
                />
                Theo dõi tồn kho
              </label>
              <p className="mt-1 text-xs text-slate-500">Tắt tùy chọn này nếu dịch vụ không giới hạn số lượng.</p>
              {form.track_inventory && (
                <Input
                  className="mt-3"
                  required
                  type="number"
                  min="0"
                  step="1"
                  label="Số lượng"
                  value={form.stock_quantity}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      stock_quantity: Number(event.target.value),
                    })
                  }
                />
              )}
            </div>
          <fieldset>
            <legend className="text-sm font-medium">
              Môn thể thao áp dụng
            </legend>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {sports.map((sport) => (
                <label
                  key={sport}
                  className="flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm"
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-brand-600"
                    checked={form.sports.includes(sport)}
                    onChange={() =>
                      setForm({
                        ...form,
                        sports: form.sports.includes(sport)
                          ? form.sports.filter((item) => item !== sport)
                          : [...form.sports, sport],
                      })
                    }
                  />
                  <span>{sport}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              className="accent-brand-600"
              checked={form.status === "ACTIVE"}
              onChange={(event) =>
                setForm({
                  ...form,
                  status: event.target.checked ? "ACTIVE" : "INACTIVE",
                })
              }
            />
            Bật ngay sau khi lưu
          </label>
          <Button type="submit" className="w-full" loading={saving}>
            {editing ? "Lưu thay đổi" : "Thêm sản phẩm"}
          </Button>
        </form>
      </Modal>
      <Modal open={catalogOpen} onClose={() => setCatalogOpen(false)} title="Catalog dịch vụ & sản phẩm gợi ý">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">Catalog được seed trong database. Chọn một hoặc nhiều mẫu; sản phẩm được thêm ở trạng thái tắt, giá và số lượng bằng 0 để OWNER cấu hình trước khi sử dụng.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium">Cơ sở<select className="field mt-1.5" value={catalogFacilityId || facilities[0]?.id || 0} onChange={(event) => {
              const id = Number(event.target.value);
              const facility = facilities.find((item) => item.id === id);
              const nextSport = facility?.sports?.[0] || "Dùng chung";
              setCatalogFacilityId(id);
              void loadCatalog(nextSport);
            }}>{facilities.map((facility) => <option key={facility.id} value={facility.id}>{facility.name}</option>)}</select></label>
            <label className="block text-sm font-medium">Môn thể thao<select className="field mt-1.5" value={catalogSports.includes(catalogSport) ? catalogSport : catalogSports[0]} onChange={(event) => void loadCatalog(event.target.value)}>{catalogSports.map((sport) => <option key={sport} value={sport}>{sport}</option>)}</select></label>
          </div>
          {catalogLoading ? <LoadingSkeleton lines={5} /> : (
            <div className="grid max-h-[55vh] gap-2 overflow-y-auto sm:grid-cols-2">
              {catalog.map((suggestion) => (
                <button key={suggestion.key} type="button" onClick={() => setCatalogSelected((current) => current.includes(suggestion.key) ? current.filter((key) => key !== suggestion.key) : [...current, suggestion.key])} className={`rounded-xl border p-3 text-left ${catalogSelected.includes(suggestion.key) ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:border-brand-400"}`}>
                  <b className="block">{suggestion.name}</b>
                  <small className="text-slate-500">{suggestion.sport} · {typeLabel[suggestion.product_type]} · {suggestion.unit}</small>
                </button>
              ))}
              {!catalog.length && <p className="text-sm text-slate-500">Chưa có gợi ý cho môn này.</p>}
            </div>
          )}
          <Button className="w-full" loading={saving} disabled={!catalogSelected.length} onClick={() => void importCatalog()}>Thêm {catalogSelected.length || ""} mục vào cơ sở</Button>
        </div>
      </Modal>
      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(undefined)}
        onConfirm={() => void confirmedAction()}
        danger={
          confirm?.kind === "delete" || confirm?.kind === "stockout" || confirm?.product.status === "ACTIVE"
        }
        title={
          confirm?.kind === "delete"
            ? "Xóa mềm sản phẩm?"
            : confirm?.kind === "stockout"
              ? "Đánh dấu hết hàng?"
            : confirm?.product.status === "ACTIVE"
              ? "Tắt sản phẩm?"
              : "Bật sản phẩm?"
        }
        description={
          confirm?.kind === "delete"
            ? "Sản phẩm sẽ ngừng sử dụng và được lưu trữ. Booking, payment và hóa đơn cũ vẫn giữ nguyên dữ liệu snapshot."
            : confirm?.kind === "stockout"
              ? "Số lượng khả dụng sẽ được đưa về 0. Bạn có thể nhập thêm số lượng trong thao tác Sửa để bán lại."
            : confirm?.product.status === "ACTIVE"
              ? "Sản phẩm sẽ ngừng hoạt động nhưng lịch sử vẫn được giữ nguyên."
              : "Sản phẩm sẽ hoạt động trở lại."
        }
        confirmLabel={
          confirm?.kind === "delete"
            ? "Xóa mềm"
            : confirm?.kind === "stockout"
              ? "Đánh dấu hết hàng"
              : "Xác nhận"
        }
      />
    </>
  );
}

function Filter({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: string[][];
}) {
  return (
    <select
      aria-label="Bộ lọc"
      className="field"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {options.map(([key, label]) => (
        <option key={key} value={key}>
          {label}
        </option>
      ))}
    </select>
  );
}
