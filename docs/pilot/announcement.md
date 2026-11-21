# Announcement draft

Post to [OSM Community forum, General talk](https://community.openstreetmap.org/c/general/38) (tags: `vietnam`, `organised-editing`), then link it from the [talk-vi list](https://lists.openstreetmap.org/listinfo/talk-vi/) and the [OSM Vietnam Facebook group](https://www.facebook.com/groups/openstreetmapvietnam/) with the Vietnamese text. Replace `<WIKI PAGE>` and `<YOUR NAME>` first. Post at least 2 weeks before step 4 of the [kit](README.md).

---

**Title:** Proposal: surface=paved/unpaved for about PILOT_N small roads in Ô Môn (Cần Thơ) from KartaView photos, reviewed by hand

Hi all,

I'm working on [vn-road-mapper](https://github.com/lector2002/vn-road-mapper), an open-source tool that looks at public street-level photos of Vietnamese rural roads and suggests a `surface` tag for the OSM way the photos were taken on. The aim is to help riders, ambulances and health stations know which small roads are paved, especially in the rainy season. Most small roads in Vietnam have no `surface` tag yet.

Before anything is edited I'd like your opinion on a small pilot:

- **Where:** the former Ô Môn district of Cần Thơ, around Long Hưng and Phước Thới, along two public KartaView rides from May 2023.
- **What:** PILOT_N ways (PILOT_UNPAVED unpaved, PILOT_PAVED paved) tagged `highway=unclassified/residential/track/service/tertiary/living_street/road` that have no `surface` tag today. Only `surface=paved` or `surface=unpaved`; no other tag is touched and no existing tag is changed.
- **How:** a MapRoulette challenge. Each task shows the way and links to 3 of the photos that voted. A person looks, then confirms, changes or skips the tag; nothing is uploaded by a script.
- **Proposals:** [list](https://github.com/lector2002/vn-road-mapper/blob/main/docs/pilot/data/pilot.csv) and [map](https://github.com/lector2002/vn-road-mapper/blob/main/docs/pilot/data/review.html) (download and open in a browser).
- **Stop rule:** if mappers reject more than 10% of the proposals, the pilot stops and the model is fixed before anything else is proposed.
- **Wiki page:** <WIKI PAGE>

**How good is it?** A ride is split into photos, each photo is matched to an OSM way, and a way gets a tag only when at least 5 photos voted and at least 70% agreed. On a test set of 4 public Vietnamese rides it calls 119 of 129 clear photos correctly; the most common mistake is an unpaved road called paved (8 of 36), while paved roads are almost never called unpaved (2 of 93). The project made those labels and I checked a blind sample of 50 photos (I agreed on 37 of 38). None of the test rides is in the Mekong delta (they are in Ninh Bình, Hà Tĩnh and Gia Lai), so the pilot is the real test for the Mekong delta. The method and numbers are [here](https://github.com/lector2002/vn-road-mapper/blob/main/docs/roadmap.md).

Questions I'd especially like answered:

1. Is `paved`/`unpaved` useful, or would you rather wait for a more specific value (`concrete`, `asphalt`, `dirt`...)?
2. Is 2023 imagery recent enough for this area?
3. Is a MapRoulette challenge the right way to do the review, or would you prefer something else?
4. Would anyone local like to review some of the tasks?

I'll wait at least two weeks for comments before starting, and change or drop the plan if the community prefers.

Thanks,
<YOUR NAME>

---

**Tiêu đề:** Đề xuất: gắn surface=paved/unpaved cho khoảng PILOT_N đường nhỏ ở Ô Môn (Cần Thơ) từ ảnh KartaView, có người kiểm tra từng đường

Chào mọi người,

Mình đang làm [vn-road-mapper](https://github.com/lector2002/vn-road-mapper), một công cụ mã nguồn mở xem ảnh đường phố công khai ở nông thôn Việt Nam và gợi ý thẻ `surface` cho đường OSM nơi ảnh được chụp. Mục tiêu là giúp người đi xe máy, xe cứu thương và trạm y tế biết đường nhỏ nào đã trải nhựa/bê tông, nhất là vào mùa mưa. Phần lớn đường nhỏ ở Việt Nam chưa có thẻ `surface`.

Trước khi sửa gì, mình muốn hỏi ý kiến mọi người về một thí điểm nhỏ:

- **Ở đâu:** quận Ô Môn cũ của Cần Thơ, quanh Long Hưng và Phước Thới, dọc hai chuyến ghi ảnh KartaView công khai tháng 5/2023.
- **Làm gì:** PILOT_N đường (PILOT_UNPAVED đường đất, PILOT_PAVED đường đã trải mặt) có thẻ `highway=unclassified/residential/track/service/tertiary/living_street/road` và hiện chưa có thẻ `surface`. Chỉ thêm `surface=paved` hoặc `surface=unpaved`; không đụng đến thẻ nào khác và không sửa thẻ đã có.
- **Cách làm:** một thử thách MapRoulette. Mỗi nhiệm vụ hiện con đường và đường dẫn tới 3 ảnh đã bỏ phiếu. Người làm xem ảnh rồi xác nhận, sửa hoặc bỏ qua; không có script nào tự tải lên.
- **Danh sách đề xuất:** [bảng](https://github.com/lector2002/vn-road-mapper/blob/main/docs/pilot/data/pilot.csv) và [bản đồ](https://github.com/lector2002/vn-road-mapper/blob/main/docs/pilot/data/review.html) (tải về và mở bằng trình duyệt).
- **Quy tắc dừng:** nếu người kiểm tra bác bỏ hơn 10% đề xuất, thí điểm dừng lại và mô hình được sửa trước khi đề xuất thêm.
- **Trang wiki:** <WIKI PAGE>

**Độ chính xác:** mỗi chuyến đi được tách thành ảnh, mỗi ảnh được gắn vào một đường OSM, và một đường chỉ được đề xuất khi có ít nhất 5 ảnh bỏ phiếu và ít nhất 70% đồng ý. Trên bộ kiểm tra gồm 4 chuyến đi công khai ở Việt Nam, mô hình đúng 119/129 ảnh rõ; lỗi hay gặp nhất là đường chưa trải mặt bị gọi là đã trải mặt (8/36), còn đường đã trải mặt rất hiếm khi bị gọi sai (2/93). Nhãn do dự án làm, và mình đã tự kiểm tra mù 50 ảnh (đồng ý 37/38). Không chuyến nào trong bộ kiểm tra ở đồng bằng sông Cửu Long (chúng ở Ninh Bình, Hà Tĩnh và Gia Lai), nên thí điểm này mới là phép thử thật cho đồng bằng sông Cửu Long. Phương pháp và số liệu ở [đây](https://github.com/lector2002/vn-road-mapper/blob/main/docs/roadmap.md).

Mình muốn hỏi:

1. `paved`/`unpaved` có hữu ích không, hay nên chờ giá trị cụ thể hơn (`concrete`, `asphalt`, `dirt`...)?
2. Ảnh năm 2023 có đủ mới cho khu vực này không?
3. Dùng MapRoulette để kiểm tra có ổn không, hay mọi người muốn cách khác?
4. Có ai ở địa phương muốn kiểm tra giúp vài nhiệm vụ không?

Mình sẽ chờ ít nhất hai tuần để nhận góp ý trước khi bắt đầu, và sẽ thay đổi hoặc bỏ kế hoạch nếu cộng đồng muốn vậy.

Cảm ơn mọi người,
<YOUR NAME>
