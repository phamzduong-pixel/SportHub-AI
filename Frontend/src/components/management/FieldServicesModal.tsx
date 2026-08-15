import { PackagePlus, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Badge, Button, EmptyState, Input, LoadingSkeleton, Modal, useToast } from "@/components/common";
import {
  adjustInventory,
  createProduct,
  getProductCatalog,
  importProductCatalog,
  listProducts,
  setProductActive,
  unassignProductSport,
  updateProduct,
  type FacilityProduct,
  type ProductCatalogSuggestion,
  type ProductType,
} from "@/services/productService";

interface FieldContext {
  id: number;
  facility_id: number | null;
  name: string;
  sport_type: string;
}

interface EditState {
  price: number;
  unit: string;
  stock_quantity: number;
}

const typeLabel: Record<ProductType, string> = { SELL: "Bán", RENT: "Cho thuê", SERVICE: "Dịch vụ" };
const keyOf = (name: string, type: ProductType) => `${name.trim().toLocaleLowerCase("vi")}|${type}`;

export function FieldServicesModal({ field, onClose }: { field?: FieldContext; onClose: () => void }) {
  const { toast } = useToast();
  const [products, setProducts] = useState<FacilityProduct[]>([]);
  const [catalog, setCatalog] = useState<ProductCatalogSuggestion[]>([]);
  const [edits, setEdits] = useState<Record<number, EditState>>({});
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<number | "catalog" | "new">();
  const [showCreate, setShowCreate] = useState(false);
  const [newProduct, setNewProduct] = useState({
    name: "", product_type: "SERVICE" as ProductType, price: 0, unit: "lần",
    stock_quantity: 0, track_inventory: false,
  });

  const load = async () => {
    if (!field?.facility_id) return;
    setLoading(true);
    try {
      const [configured, suggestions] = await Promise.all([
        listProducts(field.facility_id, field.sport_type),
        getProductCatalog(field.sport_type),
      ]);
      setProducts(configured.filter((item) => item.status !== "ARCHIVED"));
      setCatalog(suggestions);
      setEdits(Object.fromEntries(configured.map((item) => [item.id, {
        price: item.price, unit: item.unit, stock_quantity: item.stock_quantity,
      }])));
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không tải được cấu hình dịch vụ.", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (field) void load(); }, [field?.id]);

  const configuredKeys = useMemo(
    () => new Set(products.map((item) => keyOf(item.name, item.product_type))),
    [products],
  );
  const availableCatalog = catalog.filter((item) => !configuredKeys.has(keyOf(item.name, item.product_type)));
  const merge = (product: FacilityProduct) => {
    if (product.status === "ARCHIVED") {
      setProducts((current) => current.filter((item) => item.id !== product.id));
      return;
    }
    setProducts((current) => current.some((item) => item.id === product.id)
      ? current.map((item) => item.id === product.id ? product : item)
      : [product, ...current]);
    setEdits((current) => ({ ...current, [product.id]: {
      price: product.price, unit: product.unit, stock_quantity: product.stock_quantity,
    }}));
  };

  const chooseCatalog = async (item: ProductCatalogSuggestion) => {
    if (!field?.facility_id) return;
    setSavingId("catalog");
    try {
      const [product] = await importProductCatalog({
        facility_id: field.facility_id, sport: field.sport_type, catalog_keys: [item.key],
      });
      merge(product);
      toast("Đã chọn dịch vụ. Hãy cấu hình giá, số lượng và bật hoạt động.", "success");
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không thể chọn dịch vụ.", "error");
    } finally {
      setSavingId(undefined);
    }
  };

  const saveProduct = async (product: FacilityProduct) => {
    const edit = edits[product.id];
    if (!edit || !edit.unit.trim() || edit.price < 0 || !Number.isInteger(edit.stock_quantity) || edit.stock_quantity < 0)
      return toast("Giá, đơn vị và số lượng chưa hợp lệ.", "error");
    if (edit.stock_quantity < product.reserved_quantity)
      return toast(`Số lượng không thể thấp hơn ${product.reserved_quantity} đang được giữ.`, "error");
    setSavingId(product.id);
    try {
      let saved = await updateProduct(product.id, {
        facility_id: product.facility_id, name: product.name, product_type: product.product_type,
        description: product.description, image_url: null, price: edit.price, unit: edit.unit.trim(),
        sports: product.sports, status: product.status,
      });
      if (edit.stock_quantity !== product.stock_quantity) {
        saved = await adjustInventory(product.id, {
          stock_quantity: edit.stock_quantity, track_inventory: product.track_inventory,
          note: `OWNER cập nhật từ cấu hình sân ${field?.name || ""}`,
        });
      }
      merge(saved);
      toast("Đã lưu cấu hình dịch vụ.", "success");
    } catch (error) {
      toast(error instanceof Error ? error.message : "Không thể lưu dịch vụ.", "error");
    } finally {
      setSavingId(undefined);
    }
  };

  const toggle = async (product: FacilityProduct) => {
    setSavingId(product.id);
    try { merge(await setProductActive(product.id, product.status !== "ACTIVE")); }
    catch (error) { toast(error instanceof Error ? error.message : "Không thể đổi trạng thái.", "error"); }
    finally { setSavingId(undefined); }
  };
  const stockOut = async (product: FacilityProduct) => {
    setSavingId(product.id);
    try {
      merge(await adjustInventory(product.id, {
        stock_quantity: product.reserved_quantity, track_inventory: true,
        note: `OWNER đánh dấu hết hàng từ sân ${field?.name || ""}`,
      }));
      toast("Đã đánh dấu hết hàng.", "success");
    } catch (error) { toast(error instanceof Error ? error.message : "Không thể cập nhật tồn kho.", "error"); }
    finally { setSavingId(undefined); }
  };
  const unassign = async (product: FacilityProduct) => {
    if (!field || !window.confirm(`Bỏ “${product.name}” khỏi môn ${field.sport_type}?`)) return;
    setSavingId(product.id);
    try {
      await unassignProductSport(product.id, field.sport_type);
      setProducts((current) => current.filter((item) => item.id !== product.id));
      toast("Đã bỏ dịch vụ khỏi môn của sân.", "success");
    } catch (error) { toast(error instanceof Error ? error.message : "Không thể bỏ dịch vụ.", "error"); }
    finally { setSavingId(undefined); }
  };

  const createOwn = async (event: FormEvent) => {
    event.preventDefault();
    if (!field?.facility_id) return;
    setSavingId("new");
    try {
      const saved = await createProduct({
        facility_id: field.facility_id, name: newProduct.name, product_type: newProduct.product_type,
        description: null, image_url: null, price: newProduct.price, unit: newProduct.unit,
        sports: [field.sport_type], status: "INACTIVE", stock_quantity: newProduct.stock_quantity,
        track_inventory: newProduct.track_inventory,
      });
      merge(saved);
      setShowCreate(false);
      setNewProduct({ name: "", product_type: "SERVICE", price: 0, unit: "lần", stock_quantity: 0, track_inventory: false });
      toast("Đã thêm dịch vụ riêng. Kiểm tra cấu hình rồi bật hoạt động.", "success");
    } catch (error) { toast(error instanceof Error ? error.message : "Không thể thêm dịch vụ.", "error"); }
    finally { setSavingId(undefined); }
  };

  return <Modal open={Boolean(field)} onClose={onClose} title={`Dịch vụ · ${field?.name || ""}`}
    description={field ? `Dùng chung cho các sân thuộc cùng cơ sở và môn ${field.sport_type}.` : undefined}>
    {!field?.facility_id ? <EmptyState title="Sân chưa thuộc cơ sở" description="Hãy gán sân vào một cơ sở trước khi cấu hình dịch vụ." /> : loading ? <LoadingSkeleton lines={7} /> : <div className="space-y-6">
      <section>
        <div className="flex items-center justify-between gap-3"><h3 className="font-bold">Đang áp dụng ({products.length})</h3><Button size="sm" variant="outline" leftIcon={<Plus size={15} />} onClick={() => setShowCreate(!showCreate)}>Thêm riêng</Button></div>
        {products.length ? <div className="mt-3 space-y-3">{products.map((product) => {
          const edit = edits[product.id] || { price: product.price, unit: product.unit, stock_quantity: product.stock_quantity };
          const out = product.track_inventory && product.available_quantity <= 0;
          return <article key={product.id} className="rounded-xl border p-3">
            <div className="flex flex-wrap items-start justify-between gap-2"><div><b>{product.name}</b><p className="text-xs text-slate-500">{typeLabel[product.product_type]} · {product.track_inventory ? `Đang giữ ${product.reserved_quantity}` : "Không quản lý tồn"}</p></div><Badge variant={product.status === "ACTIVE" && !out ? "success" : out ? "warning" : "neutral"}>{out ? "Hết hàng" : product.status === "ACTIVE" ? "Đang bật" : "Đang tắt"}</Badge></div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <Input type="number" min={0} label="Giá" value={edit.price} onChange={(event) => setEdits({ ...edits, [product.id]: { ...edit, price: Number(event.target.value) } })} />
              <Input label="Đơn vị" value={edit.unit} onChange={(event) => setEdits({ ...edits, [product.id]: { ...edit, unit: event.target.value } })} />
              <Input type="number" min={product.reserved_quantity} label="Số lượng" disabled={!product.track_inventory} value={edit.stock_quantity} onChange={(event) => setEdits({ ...edits, [product.id]: { ...edit, stock_quantity: Number(event.target.value) } })} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" loading={savingId === product.id} leftIcon={<Save size={14} />} onClick={() => void saveProduct(product)}>Lưu</Button><Button size="sm" variant="outline" disabled={savingId === product.id} onClick={() => void toggle(product)}>{product.status === "ACTIVE" ? "Tắt" : "Bật"}</Button>{product.track_inventory && <Button size="sm" variant="outline" disabled={savingId === product.id || out} onClick={() => void stockOut(product)}>Hết hàng</Button>}<Button size="sm" variant="danger" disabled={savingId === product.id} leftIcon={<Trash2 size={14} />} onClick={() => void unassign(product)}>Bỏ chọn</Button></div>
          </article>;
        })}</div> : <p className="mt-3 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Chưa có dịch vụ nào áp dụng cho môn này.</p>}
      </section>

      {showCreate && <form onSubmit={createOwn} className="grid gap-3 rounded-xl border border-brand-200 bg-brand-50 p-4 sm:grid-cols-2">
        <h3 className="sm:col-span-2 font-bold">Dịch vụ riêng</h3><Input required minLength={2} label="Tên" value={newProduct.name} onChange={(event) => setNewProduct({ ...newProduct, name: event.target.value })} />
        <label className="text-sm font-medium">Loại<select className="field mt-2" value={newProduct.product_type} onChange={(event) => { const type = event.target.value as ProductType; setNewProduct({ ...newProduct, product_type: type, track_inventory: type !== "SERVICE" }); }}><option value="SELL">Bán</option><option value="RENT">Cho thuê</option><option value="SERVICE">Dịch vụ</option></select></label>
        <Input type="number" min={0} required label="Giá" value={newProduct.price} onChange={(event) => setNewProduct({ ...newProduct, price: Number(event.target.value) })} /><Input required label="Đơn vị" value={newProduct.unit} onChange={(event) => setNewProduct({ ...newProduct, unit: event.target.value })} />
        <Input type="number" min={0} label="Số lượng" disabled={!newProduct.track_inventory} value={newProduct.stock_quantity} onChange={(event) => setNewProduct({ ...newProduct, stock_quantity: Number(event.target.value) })} />
        <label className="flex items-center gap-2 self-end pb-3 text-sm"><input type="checkbox" checked={newProduct.track_inventory} onChange={(event) => setNewProduct({ ...newProduct, track_inventory: event.target.checked })} /> Quản lý số lượng</label>
        <Button type="submit" loading={savingId === "new"} className="sm:col-span-2">Thêm vào môn {field.sport_type}</Button>
      </form>}

      <section><h3 className="font-bold">Catalog phù hợp</h3><p className="mt-1 text-xs text-slate-500">Dữ liệu từ catalog hệ thống, gồm dịch vụ theo môn và dịch vụ dùng chung.</p>
        {availableCatalog.length ? <div className="mt-3 grid gap-2 sm:grid-cols-2">{availableCatalog.map((item) => <article key={item.key} className="flex items-center justify-between gap-3 rounded-xl border p-3"><div><b className="text-sm">{item.name}</b><p className="text-xs text-slate-500">{typeLabel[item.product_type]} · {item.unit} · {item.sport}</p></div><Button size="sm" variant="outline" disabled={savingId === "catalog"} leftIcon={<PackagePlus size={14} />} onClick={() => void chooseCatalog(item)}>Chọn</Button></article>)}</div> : <p className="mt-3 text-sm text-slate-500">Đã chọn toàn bộ catalog phù hợp.</p>}
      </section>
    </div>}
  </Modal>;
}
